#!/usr/bin/env python3
"""
validate_data.py -- implements the "Load-time validation contract" in
reference/data-schemas.md for the skill-snes-rpg data files.

Usage:
  validate_data.py <dir-with-json-files>
      Validates characters.json, enemies.json, spells.json, items.json,
      commands.json, maps.json, elements.json found in <dir>.
  validate_data.py --self-test
      Extracts the fenced ```json Example blocks from
      ../reference/data-schemas.md, assembles them into the same seven
      collections, and validates them.

Exit 0 on pass. Exit 1 on any error, printing one line per failure:
  DATA ERROR in <collection> at <path>: <reason>

Stdlib-only. Python 3.10 safe (no match statements, no PEP 604 unions).
"""

import json
import os
import re
import sys

COLLECTION_NAMES = ["characters", "enemies", "spells", "items",
                    "commands", "maps", "elements"]

ERRORS = []
WARNINGS = []


def err(collection, path, reason):
    ERRORS.append("DATA ERROR in %s at %s: %s" % (collection, path, reason))


def warn(msg):
    WARNINGS.append("WARNING: %s" % msg)


# ---------------------------------------------------------------- loading --

def load_from_dir(d):
    data = {}
    for name in COLLECTION_NAMES:
        p = os.path.join(d, name + ".json")
        if not os.path.isfile(p):
            err(name, p, "file not found")
            data[name] = [] if name != "maps" else {}
            continue
        with open(p, "r", encoding="utf-8") as f:
            try:
                data[name] = json.load(f)
            except json.JSONDecodeError as e:
                err(name, p, "invalid JSON: %s" % e)
                data[name] = [] if name != "maps" else {}
    return data


def load_self_test():
    here = os.path.dirname(os.path.abspath(__file__))
    doc_path = os.path.join(here, "..", "reference", "data-schemas.md")
    with open(doc_path, "r", encoding="utf-8") as f:
        text = f.read()
    blocks = re.findall(r"### Example.*?```json\s*(.*?)```", text, re.DOTALL)
    if len(blocks) != len(COLLECTION_NAMES):
        err("self-test", doc_path,
            "expected %d Example blocks, found %d" %
            (len(COLLECTION_NAMES), len(blocks)))
    data = {}
    for name, block in zip(COLLECTION_NAMES, blocks):
        try:
            data[name] = json.loads(block)
        except json.JSONDecodeError as e:
            err(name, doc_path, "invalid JSON in example block: %s" % e)
            data[name] = [] if name != "maps" else {}
    return data


# ------------------------------------------------------------- structural --

def require(obj, fields, collection, path):
    for f in fields:
        if f not in obj:
            err(collection, path, "missing required field '%s'" % f)


def check_characters(items):
    if not isinstance(items, list):
        err("characters", "root", "expected an array")
        return
    if not (8 <= len(items) <= 14):
        warn("characters roster size %d is outside 8-14" % len(items))
    for i, c in enumerate(items):
        p = "characters[%d]" % i
        require(c, ["id", "name", "commandId", "baseStats", "growth",
                    "equipSlots", "innateSpellIds", "joinsAt"], "characters", p)
        stats = c.get("baseStats", {})
        for k in ["hp", "mp", "atk", "def", "mag", "spi", "spd", "lck"]:
            if k not in stats:
                err("characters", p + ".baseStats", "missing stat '%s'" % k)
        for slot in c.get("equipSlots", []):
            if slot not in ("weapon", "armor", "accessory"):
                err("characters", p + ".equipSlots", "bad slot '%s'" % slot)
        ja = c.get("joinsAt", {})
        if ja.get("epoch") not in ("verdant", "sundered", "both"):
            err("characters", p + ".joinsAt.epoch", "bad epoch '%s'" % ja.get("epoch"))


def check_enemies(items):
    if not isinstance(items, list):
        err("enemies", "root", "expected an array")
        return
    for i, e in enumerate(items):
        p = "enemies[%d]" % i
        require(e, ["id", "name", "stats", "affinity", "ai", "rewards"], "enemies", p)
        ai = e.get("ai", {})
        if "phases" not in ai or not ai.get("phases"):
            err("enemies", p + ".ai", "missing/empty phases")
        for j, ph in enumerate(ai.get("phases", [])):
            require(ph, ["hpAbove", "script"], "enemies", "%s.ai.phases[%d]" % (p, j))
        rw = e.get("rewards", {})
        require(rw, ["exp", "coin", "gp"], "enemies", p + ".rewards")


def check_spells(items):
    if not isinstance(items, list):
        err("spells", "root", "expected an array")
        return
    valid_kinds = ("damage", "heal", "status", "buff", "revive", "utility")
    for i, s in enumerate(items):
        p = "spells[%d]" % i
        require(s, ["id", "name", "mpCost", "kind", "targeting"], "spells", p)
        if s.get("kind") not in valid_kinds:
            err("spells", p + ".kind", "bad kind '%s'" % s.get("kind"))
        t = s.get("targeting", {})
        require(t, ["side", "scope"], "spells", p + ".targeting")


def check_items(items):
    if not isinstance(items, list):
        err("items", "root", "expected an array")
        return
    valid_kinds = ("consumable", "weapon", "armor", "accessory", "key", "glyphstone")
    for i, it in enumerate(items):
        p = "items[%d]" % i
        require(it, ["id", "name", "kind", "price"], "items", p)
        if it.get("kind") not in valid_kinds:
            err("items", p + ".kind", "bad kind '%s'" % it.get("kind"))
        if it.get("kind") == "glyphstone":
            g = it.get("glyphstone", {})
            require(g, ["teaches", "levelBonus"], "items", p + ".glyphstone")
            for j, t in enumerate(g.get("teaches", [])):
                require(t, ["spellId", "gpCost"], "items",
                         "%s.glyphstone.teaches[%d]" % (p, j))
                if t.get("gpCost", 0) <= 0:
                    err("items", "%s.glyphstone.teaches[%d].gpCost" % (p, j),
                        "gpCost must be > 0")


def check_commands(items):
    if not isinstance(items, list):
        err("commands", "root", "expected an array")
        return
    valid_behaviors = ("steal", "throw", "mimic", "charge", "gamble",
                        "shapeshift", "guard_ally", "scan")
    for i, c in enumerate(items):
        p = "commands[%d]" % i
        require(c, ["id", "name", "behavior", "params"], "commands", p)
        if c.get("behavior") not in valid_behaviors:
            err("commands", p + ".behavior", "bad behavior '%s'" % c.get("behavior"))


def check_maps(doc):
    if not isinstance(doc, dict):
        err("maps", "root", "expected an object")
        return
    require(doc, ["tileLegend", "encounterTables", "maps"], "maps", "root")
    for i, m in enumerate(doc.get("maps", [])):
        p = "maps.maps[%d]" % i
        require(m, ["id", "kind", "epoch", "layout", "musicId"], "maps", p)
        layout = m.get("layout", [])
        if layout and len(set(len(row) for row in layout)) > 1:
            err("maps", p + ".layout", "rows are not all the same length")


def check_elements(items):
    if not isinstance(items, list):
        err("elements", "root", "expected an array")
        return
    for i, e in enumerate(items):
        p = "elements[%d]" % i
        require(e, ["id", "name"], "elements", p)


# ------------------------------------------------------------- cross-refs --

def ids_of(items, key="id"):
    return set(i.get(key) for i in items if isinstance(i, dict) and key in i)


def check_ref(collection, path, value, valid_set, label):
    if value is None:
        return
    if value not in valid_set:
        err(collection, path, "%s '%s' does not resolve" % (label, value))


def check_refs_list(collection, path, values, valid_set, label):
    for v in values or []:
        check_ref(collection, path, v, valid_set, label)


def cross_reference_pass(data):
    characters = data["characters"] if isinstance(data["characters"], list) else []
    enemies = data["enemies"] if isinstance(data["enemies"], list) else []
    spells = data["spells"] if isinstance(data["spells"], list) else []
    items = data["items"] if isinstance(data["items"], list) else []
    commands = data["commands"] if isinstance(data["commands"], list) else []
    elements = data["elements"] if isinstance(data["elements"], list) else []
    maps_doc = data["maps"] if isinstance(data["maps"], dict) else {}

    char_ids = ids_of(characters)
    enemy_ids = ids_of(enemies)
    spell_ids = ids_of(spells)
    item_ids = ids_of(items)
    command_ids = ids_of(commands)
    element_ids = ids_of(elements)
    map_ids = ids_of(maps_doc.get("maps", []))
    table_ids = set(maps_doc.get("encounterTables", {}).keys())

    for i, c in enumerate(characters):
        p = "characters[%d]" % i
        check_ref("characters", p + ".commandId", c.get("commandId"), command_ids, "commandId")
        check_refs_list("characters", p + ".innateSpellIds", c.get("innateSpellIds"), spell_ids, "spellId")

    def act_target(act):
        # act strings look like "spell:<id>" or "summon:<enemyId>"
        if isinstance(act, str) and ":" in act:
            kind, ref = act.split(":", 1)
            return kind, ref
        return None, None

    for i, e in enumerate(enemies):
        p = "enemies[%d]" % i
        aff = e.get("affinity", {})
        for k in ("weak", "resist", "absorb", "immune"):
            check_refs_list("enemies", "%s.affinity.%s" % (p, k), aff.get(k), element_ids, "elementId")
        for j, ph in enumerate(e.get("ai", {}).get("phases", [])):
            for k, act in enumerate(ph.get("script", [])):
                kind, ref = act_target(act.get("act"))
                if kind == "spell":
                    check_ref("enemies", "%s.ai.phases[%d].script[%d].act" % (p, j, k), ref, spell_ids, "spellId")
                elif kind == "summon":
                    check_ref("enemies", "%s.ai.phases[%d].script[%d].act" % (p, j, k), ref, enemy_ids, "enemyId")
        counter = e.get("ai", {}).get("counter")
        if counter:
            check_ref("enemies", p + ".ai.counter.onElement", counter.get("onElement"), element_ids, "elementId")
            kind, ref = act_target(counter.get("act"))
            if kind == "spell":
                check_ref("enemies", p + ".ai.counter.act", ref, spell_ids, "spellId")
        rw = e.get("rewards", {})
        for j, d in enumerate(rw.get("dropTable", [])):
            check_ref("enemies", "%s.rewards.dropTable[%d].itemId" % (p, j), d.get("itemId"), item_ids, "itemId")
        steal = rw.get("stealTable", {})
        for k in ("common", "rare"):
            check_ref("enemies", p + ".rewards.stealTable." + k, steal.get(k), item_ids, "itemId")

    for i, s in enumerate(spells):
        p = "spells[%d]" % i
        check_ref("spells", p + ".element", s.get("element"), element_ids, "elementId")

    for i, it in enumerate(items):
        p = "items[%d]" % i
        eq = it.get("equip")
        if eq:
            check_ref("items", p + ".equip.element", eq.get("element"), element_ids, "elementId")
            check_refs_list("items", p + ".equip.grants.resist",
                             (eq.get("grants") or {}).get("resist"), element_ids, "elementId")
            check_refs_list("items", p + ".equip.allowedCharacterIds",
                             eq.get("allowedCharacterIds"), char_ids, "characterId")
        gs = it.get("glyphstone")
        if gs:
            for j, t in enumerate(gs.get("teaches", [])):
                check_ref("items", "%s.glyphstone.teaches[%d].spellId" % (p, j), t.get("spellId"), spell_ids, "spellId")
            check_ref("items", p + ".glyphstone.summonSpellId", gs.get("summonSpellId"), spell_ids, "spellId")

    for i, c in enumerate(commands):
        p = "commands[%d]" % i
        form_id = (c.get("params") or {}).get("formEnemyId")
        check_ref("commands", p + ".params.formEnemyId", form_id, enemy_ids, "enemyId")

    for i, e in enumerate(elements):
        p = "elements[%d]" % i
        check_refs_list("elements", p + ".opposes", e.get("opposes"), element_ids, "elementId")

    for name, table in maps_doc.get("encounterTables", {}).items():
        for j, form in enumerate(table.get("formations", [])):
            check_refs_list("maps", "encounterTables.%s.formations[%d].enemyIds" % (name, j),
                             form.get("enemyIds"), enemy_ids, "enemyId")

    for i, m in enumerate(maps_doc.get("maps", [])):
        p = "maps.maps[%d]" % i
        et = m.get("encounterTableId")
        if et is not None:
            check_ref("maps", p + ".encounterTableId", et, table_ids, "encounterTableId")
        for j, w in enumerate(m.get("warps", [])):
            check_ref("maps", "%s.warps[%d].toMapId" % (p, j), w.get("toMapId"), map_ids, "mapId")
        for j, ch in enumerate(m.get("chests", [])):
            check_ref("maps", "%s.chests[%d].itemId" % (p, j), ch.get("itemId"), item_ids, "itemId")
        for j, tr in enumerate(m.get("triggers", [])):
            check_refs_list("maps", "%s.triggers[%d].formationEnemyIds" % (p, j),
                             tr.get("formationEnemyIds"), enemy_ids, "enemyId")


# ------------------------------------------------------------------ sanity --

def sanity_pass(data):
    characters = data["characters"] if isinstance(data["characters"], list) else []
    items_ = data["items"] if isinstance(data["items"], list) else []
    maps_doc = data["maps"] if isinstance(data["maps"], dict) else {}

    seen = {}
    for i, c in enumerate(characters):
        cid = c.get("commandId")
        if cid in seen:
            err("characters", "characters[%d].commandId" % i,
                "commandId '%s' duplicated with characters[%d]" % (cid, seen[cid]))
        else:
            seen[cid] = i

    for i, it in enumerate(items_):
        gs = it.get("glyphstone")
        if gs:
            for j, t in enumerate(gs.get("teaches", [])):
                if t.get("gpCost", 1) <= 0:
                    err("items", "items[%d].glyphstone.teaches[%d].gpCost" % (i, j),
                        "gpCost must be > 0")

    maps_by_id = {m.get("id"): m for m in maps_doc.get("maps", []) if isinstance(m, dict)}
    for i, m in enumerate(maps_doc.get("maps", [])):
        p = "maps.maps[%d]" % i
        layout = m.get("layout", [])
        for j, w in enumerate(m.get("warps", [])):
            at = w.get("at", [])
            if len(at) == 2:
                col, row = at
                if not (0 <= row < len(layout) and layout and 0 <= col < len(layout[0])):
                    err("maps", "%s.warps[%d].at" % (p, j), "warp origin out of bounds")
            target = maps_by_id.get(w.get("toMapId"))
            to_pos = w.get("toPos", [])
            if target and len(to_pos) == 2:
                t_layout = target.get("layout", [])
                col, row = to_pos
                if not (0 <= row < len(t_layout) and t_layout and 0 <= col < len(t_layout[0])):
                    err("maps", "%s.warps[%d].toPos" % (p, j), "warp target out of bounds")

    if not (8 <= len(characters) <= 14):
        warn("roster size %d outside 8-14 (non-fatal)" % len(characters))


# --------------------------------------------------------------------- run --

def main():
    if len(sys.argv) != 2:
        print("usage: validate_data.py <dir-with-json-files> | --self-test")
        return 1

    if sys.argv[1] == "--self-test":
        data = load_self_test()
    else:
        data = load_from_dir(sys.argv[1])

    for name in COLLECTION_NAMES:
        if name == "maps":
            check_maps(data.get("maps", {}))
        elif name == "characters":
            check_characters(data.get("characters", []))
        elif name == "enemies":
            check_enemies(data.get("enemies", []))
        elif name == "spells":
            check_spells(data.get("spells", []))
        elif name == "items":
            check_items(data.get("items", []))
        elif name == "commands":
            check_commands(data.get("commands", []))
        elif name == "elements":
            check_elements(data.get("elements", []))

    if not ERRORS:
        cross_reference_pass(data)
        sanity_pass(data)

    for w in WARNINGS:
        print(w)
    for e in ERRORS:
        print(e)

    if ERRORS:
        print("FAIL: %d error(s)" % len(ERRORS))
        return 1
    print("PASS: all collections structurally valid, all cross-references resolve")
    return 0


if __name__ == "__main__":
    sys.exit(main())
