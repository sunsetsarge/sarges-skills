# Data Schemas Reference

JSON Schema + a filled example for every data file. In a single-file HTML5
build these are inline `const` objects; in a multi-file or Godot build they
are `.json` files. Either way the shapes are identical and **validated at
load time** (SKILL.md rules 14–15): validate structure against the schema,
then resolve every cross-reference id, then render the title screen — in that
order. On failure, render a full-screen error naming the file, the JSON path,
and the reason.

A ~60-line hand-rolled validator (type/enum/required/ref checks) is fine; a
full JSON Schema library is overkill for the single-file target. What is NOT
fine is skipping validation.

Conventions used by all schemas:
- ids are lowercase snake_case strings, unique within their file.
- `epoch` fields take `"verdant" | "sundered" | "both"` (default `"both"`).
- Every cross-file reference field name ends in `Id` or `Ids`.

---

## 1. characters.json

Roster of 8–14 playable characters. One signature `commandId` each.

### Schema

```json
{ "type": "array", "minItems": 8, "maxItems": 14, "items": {
  "type": "object",
  "required": ["id", "name", "commandId", "baseStats", "growth",
               "equipSlots", "innateSpellIds", "joinsAt"],
  "properties": {
    "id":        { "type": "string" },
    "name":      { "type": "string", "maxLength": 8 },
    "commandId": { "type": "string", "$ref": "commands.id" },
    "baseStats": { "type": "object",
      "required": ["hp","mp","atk","def","mag","spi","spd","lck"],
      "additionalProperties": { "type": "integer", "minimum": 1 } },
    "growth":    { "type": "object",
      "description": "per-level gains before softcap scaling; same keys as baseStats",
      "additionalProperties": { "type": "number", "minimum": 0 } },
    "equipSlots": { "type": "array",
      "items": { "enum": ["weapon", "armor", "accessory"] },
      "description": "one weapon, one armor, 1-2 accessory entries" },
    "innateSpellIds": { "type": "array", "items": { "$ref": "spells.id" } },
    "canUseGlyphstones": { "type": "boolean", "default": true },
    "joinsAt":   { "type": "object",
      "required": ["epoch", "flag"],
      "properties": { "epoch": { "enum": ["verdant","sundered","both"] },
                       "flag":  { "type": "string" } } },
    "spriteId":  { "type": "string" }
  } } }
```

### Example

```json
[
  {
    "id": "brannic",
    "name": "Brannic",
    "commandId": "bulwark_oath",
    "baseStats": { "hp": 48, "mp": 6, "atk": 14, "def": 12,
                   "mag": 4, "spi": 6, "spd": 34, "lck": 8 },
    "growth":    { "hp": 22, "mp": 2, "atk": 2.2, "def": 1.8,
                   "mag": 0.5, "spi": 0.8, "spd": 0.6, "lck": 0.4 },
    "equipSlots": ["weapon", "armor", "accessory", "accessory"],
    "innateSpellIds": [],
    "canUseGlyphstones": true,
    "joinsAt": { "epoch": "verdant", "flag": "story_start" },
    "spriteId": "brannic_sheet"
  },
  {
    "id": "sela",
    "name": "Sela",
    "commandId": "fate_wheel",
    "baseStats": { "hp": 30, "mp": 22, "atk": 8, "def": 7,
                   "mag": 15, "spi": 13, "spd": 55, "lck": 18 },
    "growth":    { "hp": 14, "mp": 5, "atk": 1.0, "def": 1.0,
                   "mag": 2.4, "spi": 2.0, "spd": 1.0, "lck": 1.2 },
    "equipSlots": ["weapon", "armor", "accessory"],
    "innateSpellIds": ["spark_veil"],
    "joinsAt": { "epoch": "both", "flag": "met_sela" },
    "spriteId": "sela_sheet"
  }
]
```

---

## 2. enemies.json

### Schema

```json
{ "type": "array", "items": {
  "type": "object",
  "required": ["id", "name", "stats", "affinity", "ai", "rewards"],
  "properties": {
    "id":    { "type": "string" },
    "name":  { "type": "string" },
    "boss":  { "type": "boolean", "default": false },
    "stats": { "type": "object",
      "required": ["hp","mp","atk","def","mag","spi","spd","lck"],
      "additionalProperties": { "type": "integer" } },
    "affinity": { "type": "object",
      "properties": {
        "weak":   { "type": "array", "items": { "$ref": "elements.id" } },
        "resist": { "type": "array", "items": { "$ref": "elements.id" } },
        "absorb": { "type": "array", "items": { "$ref": "elements.id" } },
        "immune": { "type": "array", "items": { "$ref": "elements.id" } } } },
    "statusImmune": { "type": "array",
      "items": { "enum": ["venom","drowse","mute","shackle","addle",
                           "doom","stonecurse","slow","stasis"] } },
    "ai": { "type": "object",
      "required": ["phases"],
      "properties": {
        "phases": { "type": "array", "minItems": 1, "items": {
          "type": "object",
          "required": ["hpAbove", "script"],
          "properties": {
            "hpAbove": { "type": "number", "minimum": 0, "maximum": 1 },
            "script": { "type": "array", "items": {
              "type": "object",
              "required": ["act", "weight"],
              "properties": {
                "act":    { "type": "string",
                  "description": "attack | spell:<spellId> | flee | summon:<enemyId> | nothing" },
                "weight": { "type": "integer", "minimum": 1 },
                "target": { "enum": ["random","lowestHp","highestHp","all","self"] } } } },
            "onEnter": { "type": "object",
              "properties": { "message": { "type": "string" },
                               "act":     { "type": "string" } } } } } },
        "counter": { "type": "object",
          "properties": { "onElement": { "$ref": "elements.id" },
                           "onPhysical": { "type": "boolean" },
                           "act": { "type": "string" },
                           "chance": { "type": "number" } } } } },
    "rewards": { "type": "object",
      "required": ["exp", "coin", "gp"],
      "properties": {
        "exp":  { "type": "integer" },
        "coin": { "type": "integer" },
        "gp":   { "type": "integer" },
        "dropTable":  { "type": "array", "items": {
          "type": "object",
          "required": ["itemId", "chance"],
          "properties": { "itemId": { "$ref": "items.id" },
                           "chance": { "type": "number" } } } },
        "stealTable": { "type": "object",
          "properties": { "common": { "$ref": "items.id" },
                           "rare":   { "$ref": "items.id" } } } } },
    "spriteId": { "type": "string" }
  } } }
```

### Example

```json
[
  {
    "id": "cinder_husk",
    "name": "Cinder Husk",
    "stats": { "hp": 220, "mp": 40, "atk": 18, "def": 10,
               "mag": 12, "spi": 8, "spd": 38, "lck": 5 },
    "affinity": { "weak": ["tide"], "resist": [], "absorb": ["ember"], "immune": [] },
    "statusImmune": ["addle"],
    "ai": {
      "phases": [
        { "hpAbove": 0.5, "script": [
            { "act": "attack", "weight": 3 },
            { "act": "spell:ember_lash", "weight": 1 } ] },
        { "hpAbove": 0.0,
          "onEnter": { "message": "The husk's shell cracks open!" },
          "script": [
            { "act": "spell:ember_storm", "weight": 2, "target": "all" },
            { "act": "attack", "weight": 1, "target": "lowestHp" } ] }
      ],
      "counter": { "onElement": "tide", "act": "spell:ember_lash", "chance": 0.5 }
    },
    "rewards": {
      "exp": 84, "coin": 120, "gp": 3,
      "dropTable":  [ { "itemId": "ashen_salve", "chance": 0.25 } ],
      "stealTable": { "common": "tonic", "rare": "ember_charm" }
    },
    "spriteId": "cinder_husk_sprite"
  }
]
```

---

## 3. spells.json

Used by innate lists, Glyphstones, and enemy `spell:` acts alike — one pool.

### Schema

```json
{ "type": "array", "items": {
  "type": "object",
  "required": ["id", "name", "mpCost", "kind", "targeting"],
  "properties": {
    "id":     { "type": "string" },
    "name":   { "type": "string", "maxLength": 12 },
    "mpCost": { "type": "integer", "minimum": 0 },
    "kind":   { "enum": ["damage", "heal", "status", "buff", "revive", "utility"] },
    "element":    { "$ref": "elements.id" },
    "spellPower": { "type": "integer" },
    "status":     { "type": "object",
      "properties": { "id": { "type": "string" },
                       "inflictChance": { "type": "number" },
                       "remove": { "type": "boolean" } } },
    "buff": { "type": "object",
      "properties": { "stat": { "type": "string" },
                       "mult": { "type": "number" },
                       "ticks": { "type": "integer" } } },
    "targeting": { "type": "object",
      "required": ["side", "scope"],
      "properties": { "side":  { "enum": ["enemy", "ally", "any"] },
                       "scope": { "enum": ["one", "all", "self"] },
                       "splittable": { "type": "boolean",
                         "description": "all-target cast at reduced power allowed" } } },
    "usableInField": { "type": "boolean", "default": false },
    "animId": { "type": "string" }, "sfxId": { "type": "string" }
  } } }
```

### Example

```json
[
  { "id": "ember_lash", "name": "Ember Lash", "mpCost": 4, "kind": "damage",
    "element": "ember", "spellPower": 22,
    "targeting": { "side": "enemy", "scope": "one", "splittable": true },
    "animId": "flame_arc", "sfxId": "sfx_fire1" },
  { "id": "spark_veil", "name": "Spark Veil", "mpCost": 6, "kind": "buff",
    "buff": { "stat": "def", "mult": 1.5, "ticks": 4 },
    "targeting": { "side": "ally", "scope": "one" },
    "animId": "shimmer", "sfxId": "sfx_chime" },
  { "id": "mendrain", "name": "Mendrain", "mpCost": 5, "kind": "heal",
    "spellPower": 30, "usableInField": true,
    "targeting": { "side": "ally", "scope": "one", "splittable": true },
    "animId": "green_motes", "sfxId": "sfx_heal1" }
]
```

---

## 4. items.json

Consumables, equipment, key items, throwables, and **Glyphstones** in one file
discriminated by `kind` — the Glyphstone is the magic-acquisition companion
object (SKILL.md stated default #4).

### Schema

```json
{ "type": "array", "items": {
  "type": "object",
  "required": ["id", "name", "kind", "price"],
  "properties": {
    "id":    { "type": "string" },
    "name":  { "type": "string", "maxLength": 14 },
    "kind":  { "enum": ["consumable", "weapon", "armor", "accessory",
                         "key", "glyphstone"] },
    "price": { "type": "integer", "description": "0 = not sellable/buyable" },
    "description": { "type": "string" },

    "use": { "type": "object",
      "description": "consumables only",
      "properties": { "effect": { "enum": ["restoreHp","restoreMp","cureStatus",
                                            "revive","escape","damage"] },
                       "amount": { "type": "integer" },
                       "status": { "type": "string" },
                       "inBattle": { "type": "boolean" },
                       "inField":  { "type": "boolean" } } },

    "equip": { "type": "object",
      "description": "weapon/armor/accessory only",
      "properties": { "slot": { "enum": ["weapon","armor","accessory"] },
                       "statMods": { "type": "object",
                         "additionalProperties": { "type": "integer" } },
                       "element": { "$ref": "elements.id" },
                       "grants": { "type": "object",
                         "properties": {
                           "resist": { "type": "array", "items": { "$ref": "elements.id" } },
                           "immuneStatus": { "type": "array", "items": { "type": "string" } } } },
                       "allowedCharacterIds": { "type": "array",
                         "items": { "$ref": "characters.id" },
                         "description": "omit = anyone" } } },

    "throwable": { "type": "boolean", "default": false },

    "glyphstone": { "type": "object",
      "description": "kind=glyphstone only — THE progression hook",
      "required": ["teaches", "levelBonus"],
      "properties": {
        "teaches": { "type": "array", "items": {
          "type": "object",
          "required": ["spellId", "gpCost"],
          "properties": { "spellId": { "$ref": "spells.id" },
                           "gpCost":  { "type": "integer", "minimum": 1 } } } },
        "levelBonus": { "type": "object",
          "description": "extra stat growth applied on level-up WHILE equipped",
          "additionalProperties": { "type": "number" } },
        "summonSpellId": { "$ref": "spells.id",
          "description": "optional once-per-battle evocation" } } }
  } } }
```

### Example

```json
[
  { "id": "tonic", "name": "Tonic", "kind": "consumable", "price": 50,
    "description": "Restores 50 HP.",
    "use": { "effect": "restoreHp", "amount": 50, "inBattle": true, "inField": true } },
  { "id": "quarry_edge", "name": "Quarry Edge", "kind": "weapon", "price": 480,
    "description": "A miner's blade honed on stone.",
    "equip": { "slot": "weapon", "statMods": { "atk": 12 }, "element": "stone",
               "allowedCharacterIds": ["brannic"] },
    "throwable": true },
  { "id": "tidebound_glyph", "name": "Tidebound", "kind": "glyphstone", "price": 0,
    "description": "A Glyphstone humming with drowned voices.",
    "glyphstone": {
      "teaches": [ { "spellId": "mendrain", "gpCost": 25 },
                   { "spellId": "ember_lash", "gpCost": 60 } ],
      "levelBonus": { "mag": 1, "mp": 2 },
      "summonSpellId": "tide_surge" } }
]
```

---

## 5. commands.json

Per-character signature abilities. `behavior` is one of the eight engine
behaviors (see battle-system.md §3); `params` configures it.

### Schema

```json
{ "type": "array", "items": {
  "type": "object",
  "required": ["id", "name", "behavior", "params"],
  "properties": {
    "id":       { "type": "string" },
    "name":     { "type": "string", "maxLength": 10 },
    "behavior": { "enum": ["steal", "throw", "mimic", "charge",
                            "gamble", "shapeshift", "guard_ally", "scan"] },
    "params":   { "type": "object",
      "description": "behavior-specific; validated per behavior",
      "properties": {
        "baseChance":   { "type": "number" },
        "powerMod":     { "type": "number" },
        "chargeLevels": { "type": "array", "items": { "type": "number" } },
        "wheel":        { "type": "array", "items": {
          "type": "object",
          "required": ["weight", "effect"],
          "properties": { "weight": { "type": "integer" },
                           "effect": { "type": "string" },
                           "amount": { "type": "number" } } } },
        "formEnemyId":  { "$ref": "enemies.id" },
        "revertHpFrac": { "type": "number" } } },
    "description": { "type": "string" }
  } } }
```

### Example

```json
[
  { "id": "bulwark_oath", "name": "Bulwark", "behavior": "guard_ally",
    "params": { "powerMod": 0.5 },
    "description": "Shields an ally, taking their physical hits this round." },
  { "id": "fate_wheel", "name": "FateWheel", "behavior": "gamble",
    "params": { "wheel": [
      { "weight": 4, "effect": "damage",     "amount": 1.5 },
      { "weight": 3, "effect": "healParty",  "amount": 0.3 },
      { "weight": 4, "effect": "dud" },
      { "weight": 1, "effect": "damageAll",  "amount": 3.0 },
      { "weight": 2, "effect": "selfHurt",   "amount": 0.25 } ] },
    "description": "Spin the wheel. Anything can happen. Anything." }
]
```

---

## 6. maps.json

Tile layouts, warps, NPCs, chests, triggers, encounter tables. Layouts are
row-strings into a tile legend to keep JSON human-editable.

### Schema

```json
{ "type": "object",
  "required": ["tileLegend", "encounterTables", "maps"],
  "properties": {
    "tileLegend": { "type": "object",
      "description": "single char -> tile def",
      "additionalProperties": { "type": "object",
        "required": ["type"],
        "properties": { "type": { "type": "string" },
                         "passable": { "type": "array",
                           "items": { "enum": ["foot","ship","skyskiff"] } },
                         "encounterWeight": { "type": "number",
                           "description": "step cost multiplier; 0 = safe tile" } } } },
    "encounterTables": { "type": "object",
      "additionalProperties": { "type": "object",
        "required": ["baseSteps", "variance", "formations"],
        "properties": {
          "baseSteps":  { "type": "integer" },
          "variance":   { "type": "integer" },
          "formations": { "type": "array", "items": {
            "type": "object",
            "required": ["enemyIds", "weight"],
            "properties": { "enemyIds": { "type": "array",
                              "items": { "$ref": "enemies.id" } },
                             "weight":   { "type": "integer" },
                             "noFlee":   { "type": "boolean" } } } } } } },
    "maps": { "type": "array", "items": {
      "type": "object",
      "required": ["id", "kind", "epoch", "layout", "musicId"],
      "properties": {
        "id":     { "type": "string" },
        "kind":   { "enum": ["world", "town", "dungeon", "interior"] },
        "epoch":  { "enum": ["verdant", "sundered", "both"] },
        "layout": { "type": "array", "items": { "type": "string" },
          "description": "rows of tileLegend chars, equal length" },
        "musicId": { "type": "string" },
        "encounterTableId": { "type": "string",
          "description": "omit = no random encounters" },
        "warps": { "type": "array", "items": {
          "type": "object",
          "required": ["at", "toMapId", "toPos"],
          "properties": { "at":      { "type": "array", "items": { "type": "integer" } },
                           "toMapId": { "type": "string" },
                           "toPos":   { "type": "array", "items": { "type": "integer" } },
                           "facing":  { "enum": ["up","down","left","right"] } } } },
        "npcs": { "type": "array", "items": {
          "type": "object",
          "required": ["id", "pos", "dialogue"],
          "properties": { "id": { "type": "string" },
                           "pos": { "type": "array", "items": { "type": "integer" } },
                           "spriteId": { "type": "string" },
                           "wander": { "type": "boolean" },
                           "shopId": { "type": "string" },
                           "inn": { "type": "object",
                             "properties": { "price": { "type": "integer" } } },
                           "dialogue": { "type": "array", "items": {
                             "type": "object",
                             "required": ["lines"],
                             "properties": {
                               "ifFlags":  { "type": "array", "items": { "type": "string" } },
                               "lines":    { "type": "array", "items": { "type": "string" } },
                               "setFlags": { "type": "array", "items": { "type": "string" } } } } } } } },
        "chests": { "type": "array", "items": {
          "type": "object",
          "required": ["id", "pos", "itemId"],
          "properties": { "id": { "type": "string" },
                           "pos": { "type": "array", "items": { "type": "integer" } },
                           "itemId": { "$ref": "items.id" },
                           "count": { "type": "integer", "default": 1 } } } },
        "triggers": { "type": "array", "items": {
          "type": "object",
          "required": ["pos", "kind"],
          "properties": { "pos": { "type": "array", "items": { "type": "integer" } },
                           "kind": { "enum": ["boss","miniboss","cutscene","saveSigil"] },
                           "formationEnemyIds": { "type": "array",
                             "items": { "$ref": "enemies.id" } },
                           "onceFlag": { "type": "string" } } } },
        "shops": { "type": "object",
          "additionalProperties": { "type": "object",
            "required": ["itemIds"],
            "properties": { "itemIds": { "type": "array", "items": { "$ref": "items.id" } },
                             "epoch": { "enum": ["verdant","sundered","both"] } } } }
      } } } } }
```

### Example (abbreviated)

```json
{
  "tileLegend": {
    "g": { "type": "grass",    "passable": ["foot","skyskiff"], "encounterWeight": 1 },
    "f": { "type": "forest",   "passable": ["foot"],            "encounterWeight": 1.5 },
    "m": { "type": "mountain", "passable": [] },
    "~": { "type": "sea",      "passable": ["ship"],            "encounterWeight": 1 },
    ".": { "type": "floor",    "passable": ["foot"],            "encounterWeight": 1 },
    "#": { "type": "wall",     "passable": [] }
  },
  "encounterTables": {
    "scald_flats": { "baseSteps": 12, "variance": 4, "formations": [
      { "enemyIds": ["cinder_husk"],                "weight": 3 },
      { "enemyIds": ["cinder_husk","cinder_husk"],  "weight": 1 } ] }
  },
  "maps": [
    { "id": "scald_caverns_f1", "kind": "dungeon", "epoch": "verdant",
      "musicId": "bgm_dungeon1", "encounterTableId": "scald_flats",
      "layout": [ "########", "#......#", "#.####.#", "#......#", "########" ],
      "warps":  [ { "at": [1,1], "toMapId": "world_verdant", "toPos": [40,22], "facing": "down" } ],
      "npcs":   [],
      "chests": [ { "id": "scald_c1", "pos": [6,3], "itemId": "tonic", "count": 2 } ],
      "triggers": [ { "pos": [6,1], "kind": "saveSigil" } ] }
  ]
}
```

---

## Load-time validation contract

```
loadAllData()
  -> for each of the 6 files: structural validation against its schema
  -> cross-reference pass: every *Id/*Ids field resolves in its target file
     (commandId -> commands, spellId -> spells, itemId -> items,
      enemyIds -> enemies, encounterTableId -> encounterTables,
      toMapId -> maps, formEnemyId -> enemies, allowedCharacterIds -> characters)
  -> sanity pass: every character's commandId unique across roster;
     every map layout rectangular; every warp target in-bounds;
     every glyphstone gpCost > 0; roster size 8-14
  -> any failure: render error screen "DATA ERROR in <file> at <path>: <why>"
     and STOP. Never boot into a half-valid game.
```
