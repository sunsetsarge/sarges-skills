---
name: rpgmaker-mv-verify
description: >-
  Verify an RPG Maker MV project after ANY programmatic write, and know the
  traps in the rpgmaker-mv-ultimate MCP before you hit them. USE THIS SKILL
  whenever you generate, edit, or scaffold RPG Maker MV content — calling
  generate_map, manage_map_event, edit_map, create_database_entry, or writing
  data/*.json by hand — and ALWAYS before telling the user a map or event is
  ready. Also use it when an MV playtest crashes, shows a black screen, throws
  "Cannot read property '0' of undefined", "HTMLImageElement is in the 'broken'
  state", an NPC is stuck in a wall, a shop opens empty, or New Game instantly
  warps the player somewhere wrong. Provides a defect catalogue with symptoms,
  a verifier script that catches all of them, and the correct generate → verify
  → fix → playtest loop.
license: MIT
---

# Verifying RPG Maker MV output

MV ships no validation worth the name, and the `rpgmaker-mv-ultimate` MCP will
happily emit a project that crashes on sight while reporting success. Its own
`query_map validate` and `analyze_project critique` both scored a map **97/100
and "clean"** while that map contained a guaranteed renderer crash and two NPCs
stacked on one tile.

**Never report generated content as working without running the verifier and a
playtest.** A tool returning `{"mapId": 2}` is not evidence the map loads.

## The loop

```
generate/edit  →  rpgmv_verify.py  →  --fix  →  place events by hand  →  playtest  →  read crash-log.txt
```

```bash
python scripts/rpgmv_verify.py "<projectPath>"          # report, exit 1 if fatal
python scripts/rpgmv_verify.py "<projectPath>" --fix    # repair the safely-repairable
python scripts/rpgmv_verify.py "<projectPath>" --json   # machine-readable
```

On Windows use `C:\AI-Shared\python.exe`. `--fix` backs each file up to
`<file>.bak-verify`. It repairs autotile shapes and short shop commands; it
**never** auto-moves events, because where an NPC belongs is a judgement call.

Self-test (proves each check still fires): `python scripts/test_verify.py`
— builds fixtures from a real project, injects one defect at a time, expects 8/8.

## Defect catalogue

Every entry below was observed in the wild, not theorised.

### 1. Missing art → black screen at launch

`InvalidStateError: Failed to execute 'drawImage' ... HTMLImageElement is in the
'broken' state.` A project can ship `img/tilesets/*.txt` (the RTP's bilingual
tile-*name* metadata) with **no PNGs at all**. `Tilesets.json` names
`Outside_A1`; MV loads `img/tilesets/Outside_A1.png`; absent → broken image.

Fix: copy the RTP art from the engine's own blank template,
`<MV install>\NewData\img\`, into the project (no-clobber, to preserve custom
art). Audio usually already exists — check before assuming.

### 2. Illegal autotile shape → renderer TypeError, location-dependent

`TypeError: Cannot read property '0' of undefined` at
`ShaderTilemap._drawAutotile`. **This is the nastiest one** — it fires only when
the camera scrolls the bad tile into the paint region, so it looks random and
reproduces at one spot on the map.

MV picks one of three tables by tile *kind* but computes `shape` as
`(tileId - 2048) % 48` regardless:

| Table | Entries | Applies to |
|---|---|---|
| `FLOOR_AUTOTILE_TABLE` | 48 | A2, A1 water surfaces, A4 even rows |
| `WALL_AUTOTILE_TABLE` | 16 | A3, A4 odd rows |
| `WATERFALL_AUTOTILE_TABLE` | 4 | A1 waterfalls (kind ≥ 4 and odd) |

`generate_map` wrote A1 waterfall kinds carrying floor shapes 16–47, so
`autotileTable[shape]` was `undefined` and `table[i][0]` threw.

Repair: demote the waterfall kind to its water-surface partner (`kind - 1`),
which uses the 48-entry floor table and preserves the intended shape.

### 3. Events placed without a passability check

`generate_map`'s `enterableHouses` interiors hardcode NPCs near **(10,3)**
regardless of layout — burying every shopkeeper, innkeeper and resident inside a
wall. `manage_map_event action:"populate"` documents that it does not check
walkability.

Compute real passability from `Tilesets.json` `flags`, mirroring
`Game_Map.checkPassage`: walk layers **3→0**, skip flags with `0x10` (star / no
effect), return passable on `(flag & bit) == 0`, impassable on `(flag & bit) == bit`.
Direction bits: down `0x01`, left `0x02`, right `0x04`, up `0x08`.

Flag `0x80` is the **counter** bit — MV lets the player talk *across* it, so the
correct spot for a shopkeeper is the standable tile *behind* the counter, not
beside it. Doors and transfers legitimately sit on impassable wall tiles; do not
"fix" those.

### 4. Malformed event commands

Shop Processing (`302`) needs **5** params
`[goodsType, dataId, priceType, price, purchaseOnly]`, with `605` continuation
rows for each additional item. The generator emitted `302 [0, 0]` — two params,
pointing at database id 0, which never exists. MV skips id 0 silently, so the
shop just opens short an item with no error.

Arities worth checking: `101` Show Text 4 (and must be followed by `401`),
`201` Transfer 6, `302` Shop 5, `123` Self Switch 2. Every page must end with
code `0`.

### 5. Transfers and start position

A walk-on (`trigger: 1`) transfer sitting **on the start tile** warps the player
out the instant they press New Game. `edit_map action:"connect"` caused exactly
this. Also check transfer destinations exist and land on standable tiles.

## MCP traps (behaviour, not crashes)

- **`generate_map mode:"procedural"` silently ignores `templateId`.** You get a
  procedural map at default size with no error. Only `mode:"template"` clones a
  real template. Check the returned `width`/`height` against the template's.
- **`edit_map action:"connect"` discards `posA`, `posB` and `trigger`.** It
  places events where it likes and forces `trigger: 1`. Verify and relocate after.
- **`dryRun` is not on these schemas** despite the README claiming it is on every
  mutating tool. `generate_map` is additive (new map + MapInfos append) so it
  cannot damage existing maps; the others write immediately.
- **Generated inns are free** — `314` Recover All with no gold check.
- **`query_database entity:"tilesets"`** returns the full tile arrays and blows
  the token limit. Read `Tilesets.json` directly instead.

## Playtesting and crash traces

`manage_system { action: "playtest" }` launches through the engine's bundled
nwjs runtime — the editor does **not** need to be open, and it must not be:
**the MV editor holds `data/*.json` in memory and overwrites the whole directory
on save**, silently destroying programmatic edits.

Process liveness is not proof of success — a crashed MV sits at the same memory
and near-idle CPU as a running one, because the error screen is static. Install a
crash logger instead: alias `SceneManager.catchException` / `SceneManager.onError`
and append `e.stack` plus `$gameMap.mapId()` / `$gamePlayer.x,y` to a file via
`require('fs')`, resolving the project dir as
`path.dirname(process.mainModule.filename)` (MV's own save-path idiom). That
single trace is worth more than any amount of inference about what broke.
