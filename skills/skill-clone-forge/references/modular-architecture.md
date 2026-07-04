# Modular Architecture (Phase 3)

The signature discipline of clone-forge: the clone must be **cheap to improve
after v1**. That property is designed in at Phase 3 and proven at Phase 5 —
it cannot be added later at reasonable cost.

## The data-driven law

**Nothing a designer would want to tune is hardcoded.** All tunable
content/config lives in data; logic reads data and never embeds it.

What counts as data (non-exhaustive): entity stats, level/screen definitions,
prices and economy numbers, difficulty curves, spawn/wave tables, timings and
easings for feel, strings/copy, color/theme tokens, feature flags, keybinds,
menu structures.

Data carriers by stack:

- **Single-file HTML5:** inline `const DATA = {...}` blocks at the top of the
  file, one block per domain (`UNITS`, `LEVELS`, `TUNING`, `STRINGS`...).
  Still data-driven — the discipline is that logic only *reads* these objects.
  Graduate to separate `.json` files if the file outgrows one screen of data.
- **Godot 4:** `Resource` subclasses (`.tres`) or JSON loaded in `_ready()`;
  keep the JSON schema identical to a web build so content is engine-portable.
- **Apps:** JSON config + a typed loader; user-visible strings and workflow
  definitions in data.

**Schema first.** Write the data schema *before* the systems that consume it —
the schema is the contract between content and logic. Add a **load-time
validator** (shape + ranges + referential integrity: every `spawns: "grunt"`
must name a defined entity). A validator turns a typo'd data file from a
silent gameplay bug into an immediate error with a path. Cheap: ~50 lines.
Run it in CI/smoke tests.

## Module boundaries

Each system is a swappable module with an explicit, written contract:

```
Module: <name>
Reads:    <data blocks + which other modules' outputs>
Writes:   <state it owns — one owner per piece of state>
Events:   <emits / listens>  (prefer an event bus over direct calls for
                              cross-module effects — audio, particles, achievements)
Never:    <what it must not touch>
```

Typical game module map: input → simulation (entities, physics, combat) →
content/director (levels, spawns, difficulty) → presentation (render, audio,
juice) → meta (menus, save, settings). Typical app map: data layer → domain
logic → workflow/screens → presentation components → integrations.

Two hard rules:

1. **One owner per piece of state.** Shared mutable state between modules is
   how "swappable" quietly becomes "welded."
2. **Presentation is downstream.** Render/audio/juice reads simulation state
   and listens to events; simulation never calls into presentation. This is
   what makes feel tunable without touching logic.

## The extension-point registry

The registry is a table in `ARCHITECTURE.md` naming every seam where a future
improvement plugs in. Each row is a **promise with a test**:

| Extension point | To add one, you... | Touches logic? | Exercised? |
|---|---|---|---|
| New level | Add an entry to `LEVELS` | No | ☐ |
| New enemy | Add entry to `UNITS`; optional behavior module if novel AI | Data-only for existing behaviors | ☐ |
| New weapon/fire mode | Add entry to `WEAPONS` referencing a behavior key | No | ☐ |
| New game mode / screen | New mode module implementing the mode contract; register in `MODES` | New module, no edits to existing ones | ☐ |
| Rebalance | Edit `TUNING` only | No | ☐ |
| Retheme / new city / new dataset | Swap the data pack | No | ☐ |

Design rules for good seams:

- Minimum **3 registered seams** for v1; the plan's v2 items should each map
  to a seam (if a planned improvement has no seam, the architecture is wrong).
- Behavior variety through **data-selected behavior keys** (`ai: "charger"`,
  `pattern: "sine"`) so new content combines existing behaviors without code.
- Genuinely novel behavior = a **new module** registered in a lookup table —
  added, never edited into existing modules.
- Phase 5 exercises at least one seam through data only. Registry rows that
  fail that test get fixed, not excused.

## Stack-picker

| Situation | Stack | Why |
|---|---|---|
| Web game or app, desktop-first | **Single-file HTML5 + vanilla JS** (Canvas/DOM + Web Audio, no build step) | Ships anywhere, iteration = page reload, whole program is greppable, agents edit one file |
| Targeting mobile/native from Windows | **Godot 4 / GDScript** | Only house path to mobile exports; resources are data-driven by design |
| Terminal/CLI tool clone | Node or Python single-entry + JSON config | Same data-driven law applies |
| Target genuinely demands heavy infra (netcode, huge asset pipeline, 3D) | Justify in `ARCHITECTURE.md` first | A framework the target doesn't need is carrying cost on every future improvement |

Default down, not up: pick the simplest stack that can hit the quality bar.
Composability lives in the data schema, not the framework.

## Smells that predict expensive improvements

- A number appears in a logic file (speed, price, timing) — move it to `TUNING`.
- `if (level === 3)` — level 3 needs a data field saying what's special about it.
- Copy-pasting an entity to make a variant — variants are data rows.
- A switch statement growing a case per content item — replace with a
  data-keyed lookup of behavior modules.
- "To change X you edit three files" — X has no owner; give it one.
