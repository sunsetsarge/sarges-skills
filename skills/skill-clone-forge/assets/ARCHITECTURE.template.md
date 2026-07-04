# ARCHITECTURE — <Clone Name>

**Stack:** <from the stack-picker> — <one line of why>
**Law:** all tunable content/config in data; logic reads data; nothing a
designer would tune is hardcoded. Schema before systems.

## Module map

<Diagram or list; presentation is downstream of simulation/domain; one owner
per piece of state.>

| Module | Reads | Writes (owns) | Events (emits/listens) | Never touches |
|---|---|---|---|---|
| input | raw events | intent state | emits `intent:*` | render, data files |
| <sim/domain> | DATA.*, intent | world/domain state | emits `event:*` | render/audio |
| <content/director> | DATA.LEVELS, world state | spawn/progress state | | |
| presentation | world state (read-only) | nothing in sim | listens `event:*` | sim state writes |
| meta (menus/save/settings) | | save file, settings | | |

## Data schema

One block per domain. Define shape + ranges + references here; the load-time
validator enforces it (shape, ranges, referential integrity — every key
reference must resolve).

```js
// DATA.TUNING  — every feel/balance number lives here
{ playerSpeed: 220, jumpApexMs: 350, hitStopMs: 45, /* ... */ }

// DATA.UNITS / ENTITIES — variants are rows, behavior is a data-selected key
{ id: "grunt", hp: 20, speed: 80, ai: "charger", drops: ["coin"] }

// DATA.LEVELS / SCREENS — content is entries, never code
{ id: "L1", waves: [...], introduces: ["grunt"], tileset: "beach" }

// DATA.STRINGS — all user-visible copy
```

**Validator:** <path> — runs at load and in smoke tests; fails loud with a
path to the offending entry.

## Extension-point registry

Promises with tests. Phase 5 exercises at least one row through data only
(`git diff` must show data files only). Minimum 3 rows; every v2 item in
CLONE_PLAN.md must map to a row here.

| Extension point | To add one, you... | Touches logic? | Exercised at gate? |
|---|---|---|---|
| New level/screen | add entry to `DATA.LEVELS` | no | ☐ |
| New entity variant | add row to `DATA.UNITS` using existing behavior keys | no | ☐ |
| New behavior | new module registered in behavior lookup | new module only, no edits to existing | ☐ |
| New mode/screen flow | new mode module registered in `MODES` | new module only | ☐ |
| Rebalance / retune feel | edit `DATA.TUNING` | no | ☐ |
| Retheme / new data pack | swap data pack | no | ☐ |

## State & save

<What persists, format, where; versioning strategy for save data as the
schema evolves.>

## Event catalog

| Event | Payload | Emitted by | Consumed by |
|---|---|---|---|
| | | | |

## Deliberate non-goals

<What this architecture does NOT try to support, so future sessions don't
"fix" it — e.g. no netcode, no plugin sandboxing.>
