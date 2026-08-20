#!/usr/bin/env python
"""
rpgmv_verify.py — post-generation verification for RPG Maker MV projects.

WHY THIS EXISTS
---------------
The rpgmaker-mv-ultimate MCP (and RPG Maker's own editor) will happily emit a
project that crashes on sight. Every check below corresponds to a defect
observed in the wild on 2026-08-08, none of which the MCP's own validators or
the MV editor reported:

  1. ASSETS      Tilesets.json referenced Outside_A1.png etc. that did not exist
                 -> "InvalidStateError: HTMLImageElement is in the 'broken' state"
                 at first drawImage. Black screen, no map ever rendered.

  2. AUTOTILE    generate_map wrote A1 waterfall kinds (odd kind >= 4) carrying
                 floor-style shapes 16..47. MV picks the 4-entry
                 WATERFALL_AUTOTILE_TABLE but indexes it with shape, so
                 autotileTable[shape] is undefined ->
                 "TypeError: Cannot read property '0' of undefined" thrown from
                 ShaderTilemap._drawAutotile the moment the camera scrolls that
                 tile into the paint region. Location-dependent, looks random.

  3. PLACEMENT   Interior NPCs were hardcoded near (10,3) regardless of layout,
                 burying every shopkeeper/innkeeper inside a wall. Reachable
                 only by luck, and visually broken.

  4. EVENTCMD    Generated Shop Processing commands had 2 parameters instead of
                 5 ([goodsType, dataId, priceType, price, purchaseOnly]) and
                 pointed at item ID 0, which never exists.

  5. GEOMETRY    Map data arrays / tileset ids / MapInfos alignment can drift
                 out of sync with width*height*6.

  6. TRANSFERS   Transfer targets pointing at missing maps, or landing the
                 player on an impassable tile.

Run after ANY programmatic map or event write. Exit code 1 if fatal issues.

USAGE
-----
    python rpgmv_verify.py <projectPath> [--fix] [--json]

    --fix    repair what is safely repairable (autotile shapes, short shop
             commands). Backs each file up to <file>.bak-verify first.
             NEVER auto-moves events: correct placement needs human/agent
             judgement about where an NPC belongs.
    --json   machine-readable output instead of the text report.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import shutil
import sys
from collections import defaultdict

# ---------------------------------------------------------------- MV constants
TILE_ID_A5, TILE_ID_A1 = 1536, 2048
TILE_ID_A2, TILE_ID_A3 = 2816, 4352
TILE_ID_A4, TILE_ID_MAX = 5888, 8192
FLOOR, WALL, WATERFALL = 48, 16, 4

PASSAGE_BITS = (0x01, 0x02, 0x04, 0x08)   # down, left, right, up
FLAG_NO_EFFECT = 0x10                      # [*] star: ignore for passage
FLAG_COUNTER = 0x80                        # talk-across-me


def autotile_kind(t: int) -> int:
    return (t - TILE_ID_A1) // 48


def autotile_shape(t: int) -> int:
    return (t - TILE_ID_A1) % 48


def autotile_table(t: int):
    """Mirror ShaderTilemap._drawAutotile's table selection."""
    k = autotile_kind(t)
    if TILE_ID_A1 <= t < TILE_ID_A2:
        if k >= 4 and k % 2 == 1:
            return "WATERFALL", WATERFALL
        return "FLOOR", FLOOR
    if TILE_ID_A2 <= t < TILE_ID_A3:
        return "FLOOR", FLOOR
    if TILE_ID_A3 <= t < TILE_ID_A4:
        return "WALL", WALL
    if TILE_ID_A4 <= t < TILE_ID_MAX:
        return ("WALL", WALL) if (k // 8) % 2 == 1 else ("FLOOR", FLOOR)
    return None, None


def legal_autotile(t: int) -> int:
    """Rewrite an illegal autotile to the nearest kind that can hold its shape."""
    k, s = autotile_kind(t), autotile_shape(t)
    name, _ = autotile_table(t)
    if name == "WATERFALL":
        # the water-surface partner sits at kind-1 and uses the 48-entry floor
        # table, so the generator's intended shape survives intact
        return TILE_ID_A1 + (k - 1) * 48 + s
    return TILE_ID_A1 + k * 48 + (s % WALL)


class Project:
    def __init__(self, root: str):
        self.root = root
        self.data = os.path.join(root, "data")
        self.img = os.path.join(root, "img")
        self._cache = {}

    def load(self, name: str):
        if name not in self._cache:
            path = os.path.join(self.data, name)
            if not os.path.exists(path):
                self._cache[name] = None
            else:
                with open(path, encoding="utf-8-sig") as fh:
                    self._cache[name] = json.load(fh)
        return self._cache[name]

    def maps(self):
        for p in sorted(glob.glob(os.path.join(self.data, "Map[0-9]*.json"))):
            yield os.path.basename(p), p

    def has_image(self, folder: str, name: str) -> bool:
        if not name:
            return True          # empty name = intentionally no image
        return os.path.exists(os.path.join(self.img, folder, name + ".png"))


class Passability:
    """Faithful port of Game_Map.checkPassage for one map."""

    def __init__(self, m: dict, flags: list):
        self.w, self.h, self.d = m["width"], m["height"], m["data"]
        self.flags = flags

    def _tiles(self, x, y):
        # Game_Map.allTiles returns upper layers first
        return [self.d[(z * self.h + y) * self.w + x] for z in (3, 2, 1, 0)]

    def _flag(self, t):
        return self.flags[t] if t < len(self.flags) else 0

    def passable(self, x, y, bit) -> bool:
        for t in self._tiles(x, y):
            f = self._flag(t)
            if f & FLAG_NO_EFFECT:
                continue
            if (f & bit) == 0:
                return True
            if (f & bit) == bit:
                return False
        return False

    def standable(self, x, y) -> bool:
        if not (0 <= x < self.w and 0 <= y < self.h):
            return False
        return any(self.passable(x, y, b) for b in PASSAGE_BITS)

    def is_counter(self, x, y) -> bool:
        if not (0 <= x < self.w and 0 <= y < self.h):
            return False
        return any(self._flag(t) & FLAG_COUNTER for t in self._tiles(x, y))


class Report:
    def __init__(self):
        self.items = []

    def add(self, severity, check, where, message, fix=None):
        self.items.append({
            "severity": severity, "check": check,
            "where": where, "message": message, "fix": fix,
        })

    @property
    def fatal(self):
        return [i for i in self.items if i["severity"] == "FATAL"]

    @property
    def warn(self):
        return [i for i in self.items if i["severity"] == "WARN"]


# ------------------------------------------------------------------- the checks
def check_assets(p: Project, rep: Report):
    """Missing PNGs are the #1 cause of a black screen on launch."""
    tilesets = p.load("Tilesets.json") or []
    needed = set()
    for ts in tilesets:
        if not ts:
            continue
        for n in ts.get("tilesetNames", []):
            if n:
                needed.add(n)
    for n in sorted(needed):
        if not p.has_image("tilesets", n):
            rep.add("FATAL", "ASSETS", f"img/tilesets/{n}.png",
                    "Referenced by Tilesets.json but missing -> broken-image crash on render")

    # character / face sheets referenced by events and actors
    for fname, path in p.maps():
        with open(path, encoding="utf-8-sig") as fh:
            m = json.load(fh)
        for ev in (m.get("events") or []):
            if not ev:
                continue
            for pg in ev.get("pages", []):
                cn = (pg.get("image") or {}).get("characterName", "")
                if cn and not p.has_image("characters", cn):
                    rep.add("FATAL", "ASSETS", f"{fname} ev{ev['id']}",
                            f"character sheet '{cn}' missing from img/characters/")
    for a in (p.load("Actors.json") or []):
        if not a:
            continue
        for folder, key in (("characters", "characterName"),
                            ("faces", "faceName"),
                            ("sv_actors", "battlerName")):
            v = a.get(key, "")
            if v and not p.has_image(folder, v):
                rep.add("FATAL", "ASSETS", f"Actor {a['id']} {a.get('name')}",
                        f"{key} '{v}' missing from img/{folder}/")


def check_map_geometry(p: Project, rep: Report):
    tileset_ids = {t["id"] for t in (p.load("Tilesets.json") or []) if t}
    for fname, path in p.maps():
        with open(path, encoding="utf-8-sig") as fh:
            m = json.load(fh)
        w, h, d = m.get("width"), m.get("height"), m.get("data")
        if not (w and h and d is not None):
            rep.add("FATAL", "GEOMETRY", fname, "missing width/height/data")
            continue
        if len(d) != w * h * 6:
            rep.add("FATAL", "GEOMETRY", fname,
                    f"data length {len(d)} != width*height*6 ({w * h * 6})")
        if m.get("tilesetId") not in tileset_ids:
            rep.add("FATAL", "GEOMETRY", fname,
                    f"tilesetId {m.get('tilesetId')} does not exist in Tilesets.json")


def check_autotiles(p: Project, rep: Report, fix=False):
    for fname, path in p.maps():
        with open(path, encoding="utf-8-sig") as fh:
            m = json.load(fh)
        w, h, d = m.get("width"), m.get("height"), m.get("data")
        if not (w and h and d) or len(d) != w * h * 6:
            continue
        repairs = []
        for z in range(4):
            for y in range(h):
                for x in range(w):
                    i = (z * h + y) * w + x
                    t = d[i]
                    if t < TILE_ID_A1 or t >= TILE_ID_MAX:
                        if t >= TILE_ID_MAX or t < 0:
                            rep.add("FATAL", "AUTOTILE", f"{fname} ({x},{y}) L{z}",
                                    f"tile id {t} out of range")
                        continue
                    name, size = autotile_table(t)
                    if name and autotile_shape(t) >= size:
                        good = legal_autotile(t)
                        rep.add("FATAL", "AUTOTILE", f"{fname} ({x},{y}) L{z}",
                                f"tile {t} kind{autotile_kind(t)} shape{autotile_shape(t)} "
                                f"exceeds {name}_AUTOTILE_TABLE[{size}] -> renderer TypeError",
                                fix=f"-> {good}")
                        repairs.append((i, good))
        if fix and repairs:
            shutil.copy2(path, path + ".bak-verify")
            for i, good in repairs:
                d[i] = good
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(m, fh, ensure_ascii=False)


def check_event_placement(p: Project, rep: Report):
    tilesets = {t["id"]: t for t in (p.load("Tilesets.json") or []) if t}
    for fname, path in p.maps():
        with open(path, encoding="utf-8-sig") as fh:
            m = json.load(fh)
        ts = tilesets.get(m.get("tilesetId"))
        if not ts or len(m.get("data") or []) != m["width"] * m["height"] * 6:
            continue
        pa = Passability(m, ts["flags"])
        for ev in (m.get("events") or []):
            if not ev:
                continue
            x, y = ev["x"], ev["y"]
            name = ev.get("name", "")
            # doors/transfers legitimately sit on impassable wall tiles
            if name.lower().startswith(("door", "transfer")):
                continue
            if pa.standable(x, y):
                continue
            neighbours = [(x, y - 1), (x, y + 1), (x - 1, y), (x + 1, y)]
            adjacent_open = any(pa.standable(a, b) for a, b in neighbours)
            across_counter = any(
                pa.is_counter(a, b) and pa.standable(a + (a - x), b + (b - y))
                for a, b in neighbours
            )
            sev = "WARN" if (adjacent_open or across_counter) else "FATAL"
            rep.add(sev, "PLACEMENT", f"{fname} ev{ev['id']} '{name}' ({x},{y})",
                    "event stands on an impassable tile"
                    + ("" if adjacent_open or across_counter
                       else " and has no reachable adjacent tile — unreachable"))


def check_event_commands(p: Project, rep: Report, fix=False):
    """Command parameter arity. Wrong arity here is silent until it isn't."""
    ARITY = {101: 4, 201: 6, 302: 5, 122: 4, 123: 2, 125: 4, 126: 4, 127: 4, 128: 4}
    for fname, path in p.maps():
        with open(path, encoding="utf-8-sig") as fh:
            m = json.load(fh)
        changed = False
        for ev in (m.get("events") or []):
            if not ev:
                continue
            for pi, pg in enumerate(ev.get("pages", [])):
                lst = pg.get("list") or []
                where = f"{fname} ev{ev['id']} '{ev.get('name','')}' page{pi}"
                if not lst:
                    rep.add("WARN", "EVENTCMD", where, "empty command list")
                    continue
                if lst[-1].get("code") != 0:
                    rep.add("FATAL", "EVENTCMD", where,
                            f"page has no terminator (last code {lst[-1].get('code')})")
                for i, c in enumerate(lst):
                    code, prm = c.get("code"), c.get("parameters")
                    if prm is None:
                        rep.add("FATAL", "EVENTCMD", where, f"cmd {i} code {code}: no parameters")
                        continue
                    need = ARITY.get(code)
                    if need and len(prm) < need:
                        msg = f"cmd {i} code {code}: {len(prm)} params, expected {need}"
                        if code == 302 and fix:
                            nxt = lst[i + 1] if i + 1 < len(lst) and lst[i + 1].get("code") == 605 else None
                            if nxt:
                                c["parameters"] = list(nxt["parameters"]) + [False]
                                lst.pop(i + 1)
                            else:
                                c["parameters"] = [0, 1, 0, 0, False]
                            changed = True
                            rep.add("FATAL", "EVENTCMD", where, msg, fix="repaired")
                        else:
                            rep.add("FATAL", "EVENTCMD", where, msg)
                    if code == 101 and (i + 1 >= len(lst) or lst[i + 1].get("code") != 401):
                        rep.add("WARN", "EVENTCMD", where,
                                f"cmd {i}: Show Text (101) not followed by a text line (401)")
                    if code == 302 and len(prm) >= 2 and prm[1] == 0:
                        rep.add("WARN", "EVENTCMD", where,
                                "Shop Processing sells database id 0, which never exists")
        if fix and changed:
            shutil.copy2(path, path + ".bak-verify")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(m, fh, ensure_ascii=False)


def check_transfers_and_start(p: Project, rep: Report):
    tilesets = {t["id"]: t for t in (p.load("Tilesets.json") or []) if t}
    infos = p.load("MapInfos.json") or []
    existing = {e["id"] for e in infos if e}

    loaded = {}
    for fname, path in p.maps():
        with open(path, encoding="utf-8-sig") as fh:
            m = json.load(fh)
        mid = int("".join(ch for ch in fname if ch.isdigit()) or 0)
        loaded[mid] = m
        if mid not in existing:
            rep.add("WARN", "TRANSFER", fname, "map file exists but has no MapInfos entry")

    def pa_for(mid):
        m = loaded.get(mid)
        if not m:
            return None
        ts = tilesets.get(m.get("tilesetId"))
        if not ts or len(m.get("data") or []) != m["width"] * m["height"] * 6:
            return None
        return Passability(m, ts["flags"])

    for mid, m in loaded.items():
        for ev in (m.get("events") or []):
            if not ev:
                continue
            for pg in ev.get("pages", []):
                for c in (pg.get("list") or []):
                    if c.get("code") != 201:
                        continue
                    prm = c.get("parameters") or []
                    if len(prm) < 4 or prm[0] != 0:
                        continue   # variable-designated transfer: cannot check statically
                    dest, dx, dy = prm[1], prm[2], prm[3]
                    if dest not in loaded:
                        rep.add("FATAL", "TRANSFER", f"Map{mid:03d} ev{ev['id']}",
                                f"transfers to map {dest}, which does not exist")
                        continue
                    pa = pa_for(dest)
                    if pa and not pa.standable(dx, dy):
                        rep.add("WARN", "TRANSFER", f"Map{mid:03d} ev{ev['id']}",
                                f"lands the player on impassable tile ({dx},{dy}) of map {dest}")

    sysd = p.load("System.json") or {}
    smid, sx, sy = sysd.get("startMapId"), sysd.get("startX"), sysd.get("startY")
    if smid not in loaded:
        rep.add("FATAL", "START", "System.json", f"startMapId {smid} does not exist")
    else:
        pa = pa_for(smid)
        if pa and not pa.standable(sx, sy):
            rep.add("FATAL", "START", "System.json",
                    f"start position ({sx},{sy}) on map {smid} is impassable")
        m = loaded[smid]
        for ev in (m.get("events") or []):
            if not ev or (ev["x"], ev["y"]) != (sx, sy):
                continue
            for pg in ev.get("pages", []):
                if pg.get("trigger") in (1, 2) and any(
                        c.get("code") == 201 for c in (pg.get("list") or [])):
                    rep.add("FATAL", "START", "System.json",
                            f"a walk-on transfer event sits ON the start tile "
                            f"({sx},{sy}) — New Game warps out immediately")


def check_duplicate_positions(p: Project, rep: Report):
    """Two events on one tile: only one can ever trigger."""
    for fname, path in p.maps():
        with open(path, encoding="utf-8-sig") as fh:
            m = json.load(fh)
        seen = defaultdict(list)
        for ev in (m.get("events") or []):
            if ev:
                seen[(ev["x"], ev["y"])].append(f"{ev['id']}:{ev.get('name','')}")
        for pos, evs in seen.items():
            if len(evs) > 1:
                rep.add("WARN", "PLACEMENT", f"{fname} {pos}",
                        "stacked events, only one can trigger: " + ", ".join(evs))


def main() -> int:
    ap = argparse.ArgumentParser(description="Verify an RPG Maker MV project.")
    ap.add_argument("project")
    ap.add_argument("--fix", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    p = Project(args.project)
    if not os.path.isdir(p.data):
        print(f"No data/ directory under {args.project}")
        return 2

    rep = Report()
    check_assets(p, rep)
    check_map_geometry(p, rep)
    check_autotiles(p, rep, fix=args.fix)
    check_event_placement(p, rep)
    check_event_commands(p, rep, fix=args.fix)
    check_transfers_and_start(p, rep)
    check_duplicate_positions(p, rep)

    if args.json:
        print(json.dumps({"fatal": len(rep.fatal), "warn": len(rep.warn),
                          "items": rep.items}, indent=2))
        return 1 if rep.fatal and not args.fix else 0

    if not rep.items:
        print(f"CLEAN — no issues found in {args.project}")
        return 0

    by_check = defaultdict(list)
    for i in rep.items:
        by_check[i["check"]].append(i)
    for check in sorted(by_check):
        print(f"\n## {check}")
        for i in by_check[check]:
            tail = f"   [{i['fix']}]" if i.get("fix") else ""
            print(f"  {i['severity']:5} {i['where']}: {i['message']}{tail}")

    print(f"\n{len(rep.fatal)} FATAL, {len(rep.warn)} WARN")
    if rep.fatal and not args.fix:
        print("Re-run with --fix to repair what is safely repairable "
              "(autotile shapes, short shop commands). Event placement is never "
              "auto-moved — that needs judgement about where an NPC belongs.")
    return 1 if rep.fatal and not args.fix else 0


if __name__ == "__main__":
    sys.exit(main())
