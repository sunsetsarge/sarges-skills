# Copy-paste stubs

Snippets to copy into a world JSON while authoring. See `references/world-schema.md`
for the full field reference and `references/rules-system.md` for the rules mini-language.

## Room stub

```json
"room_id": {
  "name": "Room Name",
  "description": "What the player sees here.",
  "dark": false,
  "exits": {
    "north": "other_room_id",
    "south": {"to": "locked_room_id", "door": "some_door_object_id"}
  }
}
```

## Dark room stub (needs a lit light source in scope to see)

```json
"dark_room_id": {
  "name": "Dark Room",
  "description": "You can make out little in the gloom.",
  "dark": true,
  "exits": {"up": "lit_room_id"}
}
```

## Portable object stub

```json
"object_id": {
  "name": "brass key",
  "synonyms": ["key"],
  "adjectives": ["brass", "small"],
  "description": "A small brass key.",
  "location": "room_id",
  "flags": {
    "portable": true
  }
}
```

## Fixed/scenery object stub (examinable, not takeable)

```json
"object_id": {
  "name": "fireplace",
  "synonyms": [],
  "adjectives": ["stone"],
  "description": "A cold stone fireplace, long since gone out.",
  "location": "room_id",
  "flags": {
    "fixed": true
  }
}
```

## Container stub

```json
"object_id": {
  "name": "wooden chest",
  "synonyms": ["chest"],
  "adjectives": ["wooden"],
  "description": "A sturdy wooden chest.",
  "location": "room_id",
  "flags": {
    "fixed": true,
    "container": true,
    "openable": true,
    "open": false
  }
}
```

## Supporter stub (things can be put "on" it)

```json
"object_id": {
  "name": "stone altar",
  "synonyms": ["altar"],
  "adjectives": ["stone"],
  "description": "A stone altar.",
  "location": "room_id",
  "flags": {
    "fixed": true,
    "supporter": true
  }
}
```

## Locked door / object stub (key lives on the locked object via "key")

```json
"door_object_id": {
  "name": "iron door",
  "synonyms": ["door"],
  "adjectives": ["iron"],
  "description": "A heavy iron door.",
  "location": "room_id",
  "key": "key_object_id",
  "flags": {
    "fixed": true,
    "openable": true,
    "open": false,
    "lockable": true,
    "locked": true
  }
}
```

## Light source stub (lamp/torch; "turn on"/"turn off")

```json
"lamp_id": {
  "name": "brass lamp",
  "synonyms": ["lamp"],
  "adjectives": ["brass"],
  "description": "A brass lamp.",
  "location": "room_id",
  "flags": {
    "portable": true,
    "light_source": true,
    "on": false
  }
}
```

## Readable object stub

```json
"note_id": {
  "name": "note",
  "synonyms": ["paper"],
  "adjectives": [],
  "description": "A folded note.",
  "location": "room_id",
  "flags": {
    "portable": true,
    "readable": true
  },
  "text": "The text printed when the player reads this object."
}
```

## Wearable object stub

```json
"cloak_id": {
  "name": "cloak",
  "synonyms": [],
  "adjectives": ["black"],
  "description": "A black cloak.",
  "location": "room_id",
  "flags": {
    "portable": true,
    "wearable": true,
    "worn": false
  }
}
```

## Rule stub: command trigger (verb + object [+ target])

```json
{
  "trigger": {"verb": "put", "object": "crown_id", "target": "altar_id"},
  "conditions": [
    {"object": "crown_id", "location": "inventory"}
  ],
  "effects": [
    {"move": "crown_id", "to": "on:altar_id"},
    {"score": 5},
    {"print": "You set the crown on the altar."},
    {"win": "You win!"}
  ],
  "stop": true
}
```

## Rule stub: on_enter trigger (first message on entering a room)

```json
{
  "trigger": {"on_enter": "room_id"},
  "conditions": [
    {"flag": "seen_room_intro", "equals": false}
  ],
  "effects": [
    {"set_flag": "seen_room_intro", "value": true},
    {"print": "A one-time message the first time you enter this room."}
  ]
}
```

## Rule stub: on_turn trigger (atmospheric/periodic message)

```json
{
  "trigger": {"on_turn": true},
  "conditions": [
    {"flag": "some_gate_flag", "equals": false}
  ],
  "effects": [
    {"print": "Somewhere in the dark, something drips."}
  ]
}
```

## Rule stub: on_flag trigger (fires the instant a flag's VALUE changes)

```json
{
  "trigger": {"on_flag": "alarm_tripped"},
  "conditions": [
    {"flag": "alarm_tripped", "equals": true}
  ],
  "effects": [
    {"print": "A klaxon blares somewhere overhead."},
    {"lock": "vault_door"}
  ]
}
```

Fires whenever *any* effect sets the named flag (`alarm_tripped` here) to a value different from
what it held a moment ago -- from a command rule, an `on_enter` rule, an `on_turn` rule, or even
another `on_flag` rule. Setting a flag to the value it already holds does NOT re-fire it (only
actual changes cascade). A cascade depth cap (10) prevents two on_flag rules from re-triggering
each other forever; design puzzles so on_flag chains bottom out in a couple of hops.

## Rule stub: lock effect (re-lock a door/lockable object mid-game)

```json
{
  "trigger": {"verb": "pull", "object": "lever_id"},
  "conditions": [
    {"object": "vault_door", "property": "locked", "equals": false}
  ],
  "effects": [
    {"lock": "vault_door"},
    {"print": "The lever grinds. Somewhere, a bolt slams home -- the vault door has relocked itself."}
  ]
}
```

`{"lock": "object_id"}` is the mirror of `{"unlock": "object_id"}`: it sets that object's
`locked` flag to `true` unconditionally (it does not check `lockable`; make sure the target
object's `flags.lockable` is already `true` in `objects`, same as any door meant to be
lock/unlock-able by the player).

## Rule stub: reveal a hidden exit

```json
{
  "trigger": {"verb": "pull", "object": "lever_id"},
  "conditions": [
    {"flag": "secret_revealed", "equals": false}
  ],
  "effects": [
    {"set_flag": "secret_revealed", "value": true},
    {"reveal_exit": {"room": "room_id", "direction": "east", "to": "secret_room_id"}},
    {"print": "A hidden passage grinds open to the east."}
  ]
}
```

## Rule stub: lose condition

```json
{
  "trigger": {"verb": "enter", "object": "furnace_id"},
  "conditions": [],
  "effects": [
    {"lose": "The furnace consumes you. Game over."}
  ]
}
```

## meta block stub

```json
"meta": {
  "title": "My Adventure",
  "author": "Your Name",
  "start_room": "start_room_id",
  "max_score": 10,
  "ranks": [
    [10, "Master Adventurer"],
    [5, "Junior Adventurer"],
    [0, "Amateur"]
  ]
}
```
