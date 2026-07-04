# Exploration & Encounters Reference

Overworld, towns, dungeons, vehicles, random encounters, and the two-act
world twist. Everything here is driven by `maps.json` (schema in
data-schemas.md).

## 1. Map model

Two scales, same engine:

- **World map** — one large tile grid (128×128 up), scrolls with the party
  marker, wraps optionally. Tile types: grass, forest, hill, mountain, desert,
  swamp, river, sea, shoal, road, town, dungeon, bridge.
- **Local maps** — towns, dungeon floors, interiors (typically 20×40 to
  64×64). Entered via warp tiles on the world map or other local maps.

Per-map data: tile layer(s), collision derived from tile type + an explicit
override layer, warps, NPCs, chests, triggers, encounter table id (or none),
background music id, and an `epoch` field (see §6).

Rendering: draw only the visible window ±1 tile; camera clamps to map edges
on local maps, centers on the party on the world map. 16×16 tiles at 3× zoom
(480×432-ish logical resolution) reads correctly as SNES-era.

## 2. Movement & collision

- Grid-locked, tile-to-tile tweened movement (~8 frames per tile walk). Input
  is sampled when a step completes — buffering the held direction gives the
  genre's smooth continuous walk.
- Facing changes even when the step is blocked (tap toward a wall = turn, hold
  = bump). Interact button acts on the faced tile: NPC, chest, door, sign,
  save sigil.
- Collision check order: map bounds → tile passability for current transport
  mode (foot/ship/skyskiff) → occupied by NPC/object.

## 3. Vehicles

Transport modes are per-tile-type passability sets in data (SKILL.md rule 13):

| mode | passable | boarding rule |
|---|---|---|
| foot | land tiles except mountain/sea/river | — |
| ship | sea, shoal | board at docks; unlock ~1/3 through act one |
| skyskiff (airship-analog) | flies over everything | lands only on grass/desert; the act-two opener |

- The vehicle is a map object with a position saved in game state; boarding
  swaps the party marker's transport mode, dismounting validates the target
  tile is legal for foot.
- Vehicles change the encounter rule: ship uses sea encounter tables;
  skyskiff has NO random encounters (this is the genre's pressure valve).
- Gate regions with geography: act one's continent is ringed by mountains and
  reefs; the ship opens the archipelago; the skyskiff opens everything.

## 4. Towns

- NPCs: `dialogue` arrays with optional `flagConditions` (story flags change
  lines) and `sets` (talking can set flags). Wander NPCs move 1 tile randomly
  every 1–2s within a bounded rect; never onto warps or the player.
- **Shops** (`shopId` on an NPC or door): buy/sell UI from an item-id list in
  data. Sell-back at 50%. Show stat deltas (▲▼) against equipped gear when
  browsing equipment — this one UI detail is half of what makes shops feel
  right. Shop stock lists carry `epoch` fields.
- **Inns**: pay per head → fade out → full HP/MP + status cleanse → fade in +
  a short jingle. Price scales with region progression.
- Chests/pickups in towns are fine (barrels, clocks); flag each container id
  in `openedChests` so it stays opened forever.

## 5. Dungeons

- Linear or lightly branching floors (3–6 per dungeon), each its own local
  map, linked by stair warps. Branches hold treasure, the spine holds story.
- Ingredients per dungeon: one navigation gimmick (switches, darkness radius,
  conveyor floors, falling floors — pick ONE per dungeon), 4–8 chests, one
  save sigil before the boss, one mini-boss mid-way (fixed trigger tile, not
  random), one boss with a visible door/arena.
- Boss/mini-boss triggers set a story flag so they never respawn; their tiles
  become inert after victory.
- Escape item/spell ("Ropewind") that exits to the dungeon entrance —
  standard courtesy of the genre; disable inside boss arenas.

## 6. The two-act twist (epoch flag)

One field in game state: `epoch: "verdant" | "sundered"` (SKILL.md rule 17).
The flip happens at a scripted story beat, once, irreversibly.

- Every map, shop stock list, encounter table, and roster entry carries
  `epoch: "verdant" | "sundered" | "both"`. Lookups filter by current epoch —
  the world "changes" purely by data selection.
- Same world-map footprint, different tile layer + palette bank for the
  sundered epoch (ruined towns, altered coastline) — reuse coordinates so
  player geography knowledge still pays off.
- Roster: the flip scatters the party. Act two reopens with 1–2 members and
  re-recruits the rest through optional content — each re-recruit is a
  `roster` availability record keyed to a story flag.
- Keep the story ORIGINAL and generic in the skill's outputs: a cataclysm, a
  betrayal, a sealed god waking — invent per game, never borrow a franchise
  plot beat.

## 7. Random encounters

### Step-counter trigger (default)

```js
// on entering a map or ending a battle:
enc.grace = randInt(4, 8);                     // RULE 10: grace period
enc.threshold = table.baseSteps + randInt(-table.variance, +table.variance);
enc.steps = 0;

// on each completed step onto an encounterable tile:
if (enc.grace > 0) { enc.grace--; return; }
enc.steps++;
if (enc.steps >= enc.threshold) startBattle(pickFormation(table));
```

- `baseSteps` 10–14 for dungeons, 16–24 for overworld, `variance` ~4. Swamp/
  deep-forest tiles may count as 2 steps (danger zones); roads count as 0.5.
- Alternative per-tile probability (`p ≈ 1/baseSteps` per step) is acceptable
  but keep the SAME grace-period rule — the grace period is non-negotiable
  regardless of trigger style.
- Towns and interiors have no encounter table; the skyskiff bypasses all.

### Encounter tables & formations

Tables live in `maps.json` per zone (a map can have region rects mapping to
different tables). Table = weighted list of **formations** (1–5 enemies with
layout positions). Include a rare "surprise" chance (~8%): enemies act first;
and a "vantage" chance (~5%): party acts first. Boss formations are never in
random tables — they're trigger-tile fights with `noFlee`.

## 8. Field ↔ battle transition

- On trigger: snapshot field state (map, position, facing, vehicle), run a
  transition effect (mosaic/shatter ~400ms), swap state machines (SKILL.md
  rule 12 — unregister field input, register battle input), start battle
  music via the music director.
- On battle end: victory sequence completes FIRST, then restore field state,
  re-register field input, resume field music, apply the post-battle grace
  period.
- Game over does not restore field state — it goes to title/load.

## 9. Dialogue & text boxes

- Bottom-anchored box, 3–4 lines, typewriter reveal at a Config-set speed
  (slow/normal/fast = 1/2/4 chars per frame). Page-break on overflow with a
  bounce indicator; confirm advances only on a fresh key-down edge (SKILL.md
  rules 19–20). A held confirm fast-forwards the CURRENT page's typewriter but
  never auto-advances pages.
- Support inline control codes in dialogue strings: `{name}` (character
  name), `{pause}`, `{color:n}`. Keep the set tiny.

## 10. Save system

- **Where**: world map anywhere + save sigils in dungeons/towns (SKILL.md
  stated default #1). The Save menu entry greys out elsewhere.
- **What** (rule 21): roster with per-character level/exp/base stats/equipment
  ids/learned spell ids/GP-per-glyphstone, inventory (+ counts), currency,
  story flags object, quest states, `openedChests`, `epoch`, current map id +
  tile + facing, vehicle positions/modes, Config settings, playtime seconds,
  `saveVersion`.
- **How** (HTML5): `localStorage` under a namespaced key, 3 slots + 1
  autosave slot written on map transitions. JSON-serialize the state object;
  validate schema + version on load (rule 22). Offer export/import as a
  downloadable JSON for backup — localStorage is per-browser and clearable.
- Playtime ticks only while the game loop runs unpaused.
