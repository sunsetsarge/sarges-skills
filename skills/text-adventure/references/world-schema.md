# World schema

The world JSON is the single document the engine loads (`engine.load_world(path)`). It has six
top-level keys: `meta`, `flags`, `vocabulary`, `rooms`, `objects`, `rules`. This doc covers every
field as actually read by `engine/engine.py`.

## `meta`

```json
"meta": {
  "title": "The Cellar",
  "author": "Your Name",
  "start_room": "kitchen",
  "max_score": 10,
  "ranks": [
    [10, "Master Adventurer"],
    [5, "Junior Adventurer"],
    [0, "Amateur"]
  ]
}
```

| Field | Type | Notes |
|---|---|---|
| `title` | string | Printed as the game header. Defaults to `"Untitled Adventure"` if omitted. |
| `author` | string | Not used by engine logic; documentation only. |
| `start_room` | string | Room id the player begins in. |
| `max_score` | int | Used in the `score` command and the end-of-game rank line. |
| `ranks` | list of `[threshold, title]` | End-game rank lookup: at game end, the engine sorts ranks by threshold descending and picks the first whose threshold the final score meets or exceeds. Always include a `[0, "..."]` entry as a floor, or a score below every threshold gets the fallback title `"Adventurer"`. |

## `flags`

```json
"flags": {
  "rug_moved": false,
  "barrel_searched": false
}
```

A flat dict of global booleans (or any JSON value) that rules read and set. **Declare every flag
a rule condition checks**, with its starting value -- an undeclared flag reads back as Python
`None`, which does not equal `false`/`true` in a condition check, so a rule gated on
`{"flag": "x", "equals": false}` will silently never fire if `x` was never declared.

## `vocabulary`

```json
"vocabulary": {
  "verbs": {
    "examine": ["check", "look at"]
  }
}
```

The **only** key the engine reads under `vocabulary` is `verbs` (a map of canonical verb name to
a list of extra synonym words). It is merged into (not a replacement for) the engine's built-in
`DEFAULT_VERB_SYNONYMS` table -- you only need to list *additional* synonyms, and only for verbs
you want to extend. An empty `"verbs": {}` is valid and common (the-cellar example ships one).
See `references/standard-verbs.md` for the full built-in list. The browser export in
`engine/web/template.html` reads this same `vocabulary.verbs` key with identical merge
semantics -- no schema translation is needed to hand a world JSON to either runtime (see
`references/rules-system.md`'s "Cross-runtime parity check" section for the automated test that
proves this).

## `rooms`

```json
"rooms": {
  "cellar": {
    "name": "Cellar",
    "description": "A cold, damp cellar carved from raw earth. An iron door is set into the far wall.",
    "dark": true,
    "exits": {
      "up": "kitchen",
      "north": {"to": "vault", "door": "iron_door"}
    }
  }
}
```

| Field | Type | Notes |
|---|---|---|
| `name` | string | Shown as the room header line. |
| `description` | string | Shown on first visit, and on every visit while `verbose` mode is on. |
| `dark` | bool | If true, the room has no light unless a lit `light_source` object is in scope (carried or in the room). See "Darkness" below. Omit or set `false` for a normally-lit room. |
| `exits` | dict | Direction name -> destination. Keys are canonical direction names: `north`, `south`, `east`, `west`, `up`, `down`, `in`, `out`, `northeast`, `northwest`, `southeast`, `southwest` (players may type abbreviations like `n`/`s`/`ne`; the parser canonicalizes them). |

**Exit value forms** (two allowed):
- A bare room id string: `"up": "kitchen"` -- an open, unconditional passage.
- A door-gated object: `"north": {"to": "vault", "door": "iron_door"}` -- `to` is the
  destination room id; `door` is an object id. Going that direction first checks the door
  object's flags: if `lockable` and `locked`, the player is told it's locked; if `openable` and
  not `open`, they're told it's closed; only then does the room change. The door object still
  needs its own entry under `objects` (see the `iron_door` example below) so it can be examined,
  unlocked, and opened like any other object.

Hidden exits (not present at all in `exits` until revealed) are added at runtime by a rule's
`reveal_exit` effect (see `rules-system.md`).

## `objects`

```json
"lamp": {
  "name": "brass lamp",
  "synonyms": ["lamp", "light"],
  "adjectives": ["brass"],
  "description": "A sturdy brass lamp, the kind that could burn for hours on a little oil.",
  "location": {"on": "table"},
  "flags": {
    "portable": true,
    "light_source": true,
    "on": false
  }
}
```

| Field | Type | Notes |
|---|---|---|
| `name` | string | Canonical display name; also a valid noun word for the parser. |
| `synonyms` | list of string | Extra noun words that resolve to this object (e.g. `"lamp"` for "brass lamp"). |
| `adjectives` | list of string | Words that disambiguate when two objects share a noun (e.g. `"red key"` vs `"brass key"`). |
| `description` | string | Shown by `examine`. |
| `location` | string or dict | See "Location forms" below. |
| `flags` | dict | **All object state (portable, container, open, locked, etc.) lives nested under this one `flags` sub-key** -- not as top-level fields on the object. See the flag table below. |
| `key` | string (object id) | Only meaningful on a `lockable` object: the object id of the key that locks/unlocks it. Lives at the top level of the object, *not* inside `flags`. |
| `text` | string | Only meaningful on a `readable` object: the string printed by `read`. Top level, not inside `flags`. |

### Location forms

`location` accepts:
- A room id string: `"location": "kitchen"` -- sitting directly in that room.
- `"inventory"` -- carried by the player.
- `"nowhere"` -- not present anywhere (used e.g. after an object is eaten).
- `{"in": "<container_object_id>"}` -- inside an (openable or always-open) container object.
- `{"on": "<supporter_object_id>"}` -- resting on a supporter object (e.g. a table or altar).

The same forms are used by rule `move` effects and by rule `location` conditions, with one
difference: rule conditions/effects use the string-prefixed shorthand `"in:<id>"` / `"on:<id>"`
instead of a nested dict (see `rules-system.md`).

### Flag keys

The engine normalizes every object's `flags` dict at load time so all of the following keys
always exist (defaulting to `false` if you don't set them):

`portable`, `fixed`, `container`, `open`, `openable`, `lockable`, `locked`, `key`, `supporter`,
`light_source`, `on`, `edible`, `drinkable`, `readable`, `wearable`, `worn`.

Notes on specific flags:
- `portable` defaults functionally to takeable unless `fixed` is also set -- `do_take` refuses
  if `not flags["portable"]` **or** `flags["fixed"]` is true, so scenery objects should set
  `"fixed": true` (an object with no `portable` key at all is still refused because the
  normalized default is `false`; the-cellar's scenery objects set only `fixed: true` and rely on
  that -- either approach works, but setting both explicitly is clearest).
- `container` + `open`/`openable`: a container needs `container: true` to hold items and accept
  `put ... in`; if it should start closed and be openable, add `openable: true, open: false`. A
  container with no `openable` key (like the flour barrel, which is always `open: true` and
  never closes) works fine as an always-open container.
- `supporter`: lets `put ... on` target it and lets `examine`/room descriptions surface what's on
  it.
- `light_source` + `on`: only a light source with both `light_source: true` and `on: true` (via
  `turn on <lamp>`) lifts darkness while it's in scope.
- `lockable` + `locked` + top-level `key`: the door/container needs a matching top-level `"key":
  "<key_object_id>"` field; `lock`/`unlock` check the noun-with-target object id against it.
- `readable` + top-level `text`: `read` prints `text` if set, else `"It's blank."`.
- `wearable` + `worn`: `wear`/`remove` toggle `worn`; worn items are hidden from the room's
  "You can see:" listing but still appear in `inventory`.
- `edible`: `eat` moves the object to `"nowhere"` (consumed).
- `drinkable`: `drink` prints a message but does not move the object (a potion isn't consumed by
  default -- add a rule if you want it removed after drinking).

## `rules`

A flat list, evaluated **in file order** (see `references/rules-system.md` for the full
triggers/conditions/effects reference). Minimal shape:

```json
{
  "trigger": {"verb": "put", "object": "crown", "target": "altar"},
  "conditions": [
    {"object": "crown", "location": "inventory"}
  ],
  "effects": [
    {"move": "crown", "to": "on:altar"},
    {"score": 5},
    {"print": "You set the jeweled crown upon the stone altar."},
    {"win": "The altar accepts your offering."}
  ],
  "stop": true
}
```

## One worked snippet (verified against engine.py)

```json
{
  "meta": {
    "title": "The Cellar",
    "author": "text-adventure skill example",
    "start_room": "kitchen",
    "max_score": 10,
    "ranks": [[10, "Master Adventurer"], [5, "Junior Adventurer"], [0, "Amateur"]]
  },
  "flags": { "barrel_searched": false },
  "vocabulary": { "verbs": {} },
  "rooms": {
    "kitchen": {
      "name": "Kitchen",
      "description": "A dim farmhouse kitchen. A flour barrel stands against the wall.",
      "dark": false,
      "exits": { "down": "cellar" }
    },
    "cellar": {
      "name": "Cellar",
      "description": "A cold, damp cellar. An iron door is set into the far wall.",
      "dark": true,
      "exits": { "up": "kitchen", "north": {"to": "vault", "door": "iron_door"} }
    },
    "vault": {
      "name": "Vault",
      "description": "A small stone vault. A stone altar stands in the center.",
      "dark": false,
      "exits": { "south": "cellar" }
    }
  },
  "objects": {
    "lamp": {
      "name": "brass lamp", "synonyms": ["lamp"], "adjectives": ["brass"],
      "description": "A sturdy brass lamp.",
      "location": "kitchen",
      "flags": { "portable": true, "light_source": true, "on": false }
    },
    "barrel": {
      "name": "flour barrel", "synonyms": ["barrel"], "adjectives": ["flour"],
      "description": "A barrel half full of flour.",
      "location": "kitchen",
      "flags": { "fixed": true, "container": true, "open": true }
    },
    "brass_key": {
      "name": "brass key", "synonyms": ["key"], "adjectives": ["brass"],
      "description": "A small brass key.",
      "location": {"in": "barrel"},
      "flags": { "portable": true, "key": true }
    },
    "iron_door": {
      "name": "iron door", "synonyms": ["door"], "adjectives": ["iron"],
      "description": "A heavy iron door.",
      "location": "cellar",
      "key": "brass_key",
      "flags": { "fixed": true, "openable": true, "open": false, "lockable": true, "locked": true }
    },
    "altar": {
      "name": "stone altar", "synonyms": ["altar"], "adjectives": ["stone"],
      "description": "A stone altar carved with faded runes.",
      "location": "vault",
      "flags": { "fixed": true, "supporter": true }
    },
    "crown": {
      "name": "jeweled crown", "synonyms": ["crown"], "adjectives": ["jeweled"],
      "description": "A golden crown.",
      "location": "vault",
      "flags": { "portable": true }
    }
  },
  "rules": [
    {
      "trigger": {"verb": "search", "object": "barrel"},
      "conditions": [{"flag": "barrel_searched", "equals": false}],
      "effects": [
        {"set_flag": "barrel_searched", "value": true},
        {"print": "You plunge your hands into the flour and feel something hard. A small brass key!"}
      ],
      "stop": false
    },
    {
      "trigger": {"verb": "put", "object": "crown", "target": "altar"},
      "conditions": [{"object": "crown", "location": "inventory"}],
      "effects": [
        {"move": "crown", "to": "on:altar"},
        {"score": 5},
        {"print": "You set the jeweled crown upon the stone altar."},
        {"win": "The altar accepts your offering."}
      ],
      "stop": true
    }
  ]
}
```

This is a trimmed version of `examples/the-cellar.json`; it demonstrates `meta` with ranks, a
dark room, a door-gated exit, a container with a hidden key, a lockable door, a supporter, and
two rules (a `stop: false` command rule that lets the default `search` handler still run
afterward, and a winning `put ... on ...` rule). It has been verified to load and play correctly
against `engine.py` (see this skill's build verification notes).
