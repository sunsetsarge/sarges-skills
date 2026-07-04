# Rules system

Puzzles are expressed as **declarative rules** in the world JSON's `rules` list, not as engine
code. Each rule is `{"trigger": {...}, "conditions": [...], "effects": [...], "stop": bool}`,
evaluated by `run_rules()` / `condition_met()` / `apply_effect()` in `engine.py`.

## Triggers

A rule's `trigger` dict determines *when* it is even considered. Exactly one of these shapes:

- **Command trigger** -- any combination of `verb`, `object`, `target` (all optional, but at
  least one of the three must be present, and `verb` is effectively required for the rule to
  ever be considered -- see "implementation notes" below):
  ```json
  {"trigger": {"verb": "put", "object": "crown", "target": "altar"}}
  ```
  Matches when the player's parsed command has that verb, and (if present) the resolved noun
  object id equals `object` and the resolved target object id equals `target`. Omit `object`/
  `target` to match the verb against any noun (e.g. `{"verb": "attack"}` fires on `attack`
  anything).
- **`on_enter`** -- fires when the player's current room becomes the named room id (checked on
  the initial `start_message()` and every successful `go`):
  ```json
  {"trigger": {"on_enter": "vault"}}
  ```
- **`on_turn`** -- fires at the end of every turn (after a command resolves), unconditionally
  considered every turn (conditions still gate whether it actually applies):
  ```json
  {"trigger": {"on_turn": true}}
  ```
- **`on_flag`** -- fires the instant a flag's value actually changes:
  ```json
  {"trigger": {"on_flag": "alarm_tripped"}}
  ```
  Any effect that changes a global flag's value (currently: `set_flag`, whenever the new value
  differs from what the flag held a moment before) triggers matching `on_flag` rules for that
  flag name, immediately, as part of applying the effects list that caused the change --
  regardless of whether that change came from a `command`, `on_enter`, or `on_turn` rule. Setting
  a flag to the value it already holds does **not** re-fire it (only actual value changes
  cascade). `on_flag` rules can themselves set flags, which can fire further `on_flag` rules
  (a cascade); `apply_effects()` / `_fire_on_flag()` in `engine.py` cap this cascade at
  `MAX_FLAG_CASCADE_DEPTH` (10) so two rules that flip each other's flag back and forth can't
  loop forever -- design puzzles so a cascade chain naturally bottoms out well before that depth.
  See `templates/stubs.md` for a worked stub.

## Conditions (all ANDed)

Every entry in `conditions` must be true for the rule's effects to apply. Supported shapes
(`condition_met()`):

```json
{"flag": "rug_moved", "equals": false}
{"object": "crown", "location": "inventory"}
{"object": "crown", "location": "in:some_container_id"}
{"object": "crown", "location": "on:altar"}
{"object": "iron_door", "property": "locked", "equals": false}
{"score_at_least": 5}
{"score_at_most": 9}
```

- `{"flag": ..., "equals": ...}` -- compares a global flag's current value. `equals` defaults to
  `true` if omitted.
- `{"object": ..., "location": ...}` -- checks the object's current location. `location` accepts
  a bare room id, `"inventory"`, `"nowhere"`, or the string-prefixed forms `"in:<id>"` /
  `"on:<id>"` (note: this is a **different string format** from the nested-dict `location` value
  used when *defining* an object's starting place in `world-schema.md` -- rule conditions/effects
  always use the `in:`/`on:` string prefix, never a `{"in": ...}` dict literal).
- `{"object": ..., "property": ..., "equals": ...}` -- checks one of the object's normalized
  `flags` keys (e.g. `"locked"`, `"open"`, `"on"`). `equals` defaults to `true` if omitted.
- `{"score_at_least": N}` / `{"score_at_most": N}` -- compares current score.

An empty `conditions: []` list is valid and always passes (`all([])` is `True`).

## Effects (applied in list order)

```json
{"set_flag": "rug_moved", "value": true}
{"move": "crown", "to": "on:altar"}
{"reveal_exit": {"room": "cellar", "direction": "east", "to": "secret_room"}}
{"lock_exit": {"room": "cellar", "direction": "east"}}
{"unlock": "iron_door"}
{"lock": "iron_door"}
{"print": "The runes flare with pale light."}
{"score": 5}
{"win": "You win!"}
{"lose": "You have died."}
```

Notes on exact field shapes actually read by `apply_effect()`:

- `set_flag` is the **flag name string itself** (not a nested object) and `value` is a sibling
  key -- `{"set_flag": "flag_name", "value": true}`, not `{"set_flag": {"name": ..., "value":
  ...}}`.
- `move` is the **object id string** and `to` is a sibling key -- `{"move": "crown", "to":
  "on:altar"}`. The `to` value uses the same `in:`/`on:` string-prefix convention as location
  conditions (not the nested-dict form used in the object's initial `location` field).
- `unlock` is the bare object id string; it always sets that object's `locked` flag to `false`.
  `lock` is its exact mirror -- `{"lock": "iron_door"}` -- and always sets that object's `locked`
  flag to `true` unconditionally (it does not check `lockable`; the target should already have
  `flags.lockable: true`, same as any door meant to be lockable by the player). Use it for
  "becomes locked" puzzles: a lever that re-seals a vault, a door that slams shut after an
  alarm trips, etc. See `templates/stubs.md` for a worked stub.
- `reveal_exit` / `lock_exit` take a nested `{"room", "direction", "to"}` / `{"room",
  "direction"}` dict -- these two are the only effects with a nested-dict payload.
- `win` / `lose` each take the end-of-game message string directly as the value (not nested).
  Setting either ends the game (`game_over = True`) and records `win`/message for the final rank
  line, which is appended automatically at the end of that turn.

## Evaluation order (as implemented in `Engine._execute_single`)

1. **Meta verbs** (`quit`, `restart`, `help`, `score`, `verbose`, `brief`, `undo`) are handled
   first and never reach rules.
2. If the game is already over, further commands just get a "the game has ended" message.
3. An undo snapshot is pushed.
4. The command is parsed and nouns/targets resolved (ambiguity/scope errors return immediately).
5. **Darkness gate**: if the room is unlit and the verb is not in the always-allowed set (`go`,
   `turn`, `inventory`, `wait`, `look`, `drop`), the grue message is returned immediately and
   nothing below runs.
6. **`hooks.py` `on_command`**, if present, runs first and can short-circuit everything below by
   returning a non-`None` string.
7. **Command-kind rules** are evaluated in file order via `run_rules(kind="command", ...)`. For
   each rule whose trigger matches and whose conditions all pass, its effects are applied
   immediately, `consumed` is set `True`, and — **only if that rule's `stop` field is `true`
   (the default when `stop` is omitted)** — evaluation of further command rules stops right
   there. A rule with `"stop": false` applies its effects but lets rule-matching continue (the
   default `search barrel` handler afterward, or later rules with the same trigger). If **any**
   command rule matched (`consumed`), the default verb handler for that command is skipped
   entirely for that turn.
8. If no command rule consumed the command, the **default verb handler** runs (see
   `standard-verbs.md`).
9. **End of turn** (`_end_of_turn`): turn counter increments, `hooks.py`'s `on_turn` runs if
   present, then all `on_turn`-kind rules are evaluated (no `stop` short-circuiting here --
   *every* matching `on_turn` rule with passing conditions fires every turn). If the game ended
   this turn, the end message and the computed rank line are appended.
10. `on_enter` rules run as part of step 7/8's `go` handling (or at game start), immediately
    after the room changes and before the room description is composed -- their `print` output is
    appended after the room description text.
11. **`on_flag` cascade**: whenever any of the effects applied in steps 7, 9, or 10 (or a
    previously-cascaded `on_flag` rule's own effects) change a flag's value via `set_flag`,
    matching `on_flag` rules fire immediately as part of applying that same effects list -- this
    is not a separate step in the turn loop, it happens inline inside `apply_effects()` right
    after the effects list that caused the change finishes running.

There is **no separate "win/lose check" phase** distinct from effects -- `win`/`lose` are just
effects like any other, applied inline wherever a rule that contains them fires (a command rule,
an `on_enter` rule, an `on_turn` rule, or an `on_flag` rule can all end the game).

## `hooks.py` escape hatch (Python-only)

If a file named `hooks.py` sits next to the world JSON, `engine.load_hooks()` imports it
automatically (both `play.py` and `walkthrough_runner.py` call this). It's entirely optional --
the bundled `the-cellar` example does not use one. Two optional module-level functions:

```python
def on_command(world, verb, noun, target):
    """Return a string to short-circuit the command (skip world rules AND the
    default handler), or None to let normal processing continue."""
    return None

def on_turn(world):
    """Return a string to print at the end of every turn, or None."""
    return None
```

`on_command` runs with **higher priority than world rules** (step 6 above, before step 7) --
use it sparingly, only for logic that genuinely can't be expressed as declarative
triggers/conditions/effects (e.g. procedural/random behavior, since the rules system and the
rest of the engine are deliberately deterministic).

**WARNING: `hooks.py` does NOT run in the HTML export.** `engine/web/template.html` is a
from-scratch JavaScript reimplementation of the rooms/objects/rules model with no Python
interpreter available in the browser -- there is no `hooks.py`-equivalent mechanism there at all.
If a game's win condition or any required puzzle step depends on `hooks.py`, that game **cannot
be losslessly exported to the single-file HTML runtime** -- keep puzzle logic in declarative
rules whenever browser export matters, and reserve hooks for logic you're comfortable losing (or
reimplementing by hand in JS) in that export.

## Cross-runtime parity check

`engine/engine.py` and `engine/web/template.html` reimplement the same world-model + rules
semantics independently (Python vs. JavaScript) so a single world JSON drives both runtimes
identically -- *except* for the Python-only `hooks.py` escape hatch above. `engine/web/
parity_test.mjs` is the automated regression test for this promise: it extracts the pure
engine-core JavaScript out of `template.html` (the block between the `ENGINE-CORE-START` /
`ENGINE-CORE-END` markers, which has zero DOM references so it can run standalone under Node),
runs the bundled `examples/the-cellar.json` walkthrough through it, and asserts it reaches the
same win/score/turns result as `engine/walkthrough_runner.py` gets from the Python engine. Run
`node engine/web/parity_test.mjs` after any change to either runtime's rules/effects/conditions
logic; it must print `PASS`.
