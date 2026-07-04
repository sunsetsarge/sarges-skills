# Standard verbs

The canonical verb table, pulled directly from `DEFAULT_VERB_SYNONYMS` in `engine.py`, plus each
verb's default behavior. A world's `vocabulary.verbs` can add more synonyms to any of these (see
`world-schema.md` / `parser-design.md`) but cannot rename or remove the canonical verb itself.

**All world-interaction verbs below are rule-overridable**: if a command-kind rule's trigger
matches `{verb, object, target}` and its conditions are met, the rule's effects run *instead of*
the default handler (see `rules-system.md` for exact precedence). Meta verbs (bottom of this
page) are handled before rules ever run and are not overridable.

## World-interaction verbs

| Verb | Synonyms | Default behavior |
|---|---|---|
| `look` | `l` | Full room description if unvisited or `verbose` is on; otherwise just the room name (`brief` mode). |
| `examine` | `x`, `inspect`, `describe` | Prints the object's `description`; appends its `text` if `readable`, and open/closed + contents if a `container`. |
| `inventory` | `i`, `inv` | Lists carried objects, or `"You are carrying nothing."` |
| `take` | `get`, `grab`, `pick` | Moves object to inventory unless it's already there, or `fixed`/not `portable` (`"You can't take the X."`). Supports `take all`/`take everything`. |
| `drop` | (none beyond itself) | Moves object from inventory to the current room, or `"You aren't carrying that."` Supports `drop all`/`drop everything`. |
| `go` | `walk`, `run`, `move` (+ bare direction words as shorthand) | Moves to the room named as the direction's exit target; checks door `locked`/`open` flags first if the exit is door-gated. `"You can't go that way."` if no such exit. |
| `open` | (none) | Sets `open: true` if `openable` or `container` and not `locked`; else a specific refusal (`"is locked"`, `"can't open"`, `"already open"`). |
| `close` | `shut` | Sets `open: false`; `"already closed"` if not open. |
| `lock` | (none) | Requires a target key matching the object's top-level `key` id; `"Lock it with what?"` if no target given, `"doesn't fit"` if wrong key. |
| `unlock` | (none) | Same key check as `lock`, in reverse; `"already unlocked"` if not locked. |
| `read` | (none) | Prints `text` if `readable`; else `"There's nothing to read on the X."` |
| `push` | (none) | No default puzzle effect -- `"You push the X, but nothing happens."` unless a rule overrides it. |
| `pull` | (none) | Same as `push`: no-op unless overridden by a rule. |
| `turn` | (none) | Handles `turn on X` / `turn X on` / `turn off X` / `turn X off` phrasing (prep-based or trailing on/off word); toggles `light_source` objects' `on` flag; otherwise `"...but nothing happens."` |
| `put` | `place`, `insert` | `put X in Y` requires Y `container` + `open`; `put X on Y` requires Y `supporter`. Object must be in inventory first. `"Put it where?"` if no target given. |
| `wear` | `don` | Sets `worn: true` if `wearable` and carried. |
| `remove` | `unwear`, `doff` | Sets `worn: false`; `"You aren't wearing the X."` if not worn. |
| `eat` | (none) | Consumes (`edible` only) -- moves the object to `"nowhere"`. |
| `drink` | (none) | Prints a message (`drinkable` only) -- does **not** consume the object by default; add a rule if the liquid should be used up. |
| `search` | (none) | On a `container`: lists contents if open, else `"is closed"`. On anything else: `"You find nothing special..."` |
| `enter` | (none) | No default room-entry behavior -- `"You can't enter the X."` unless a rule handles it (there is no automatic enter-as-go mapping in the Python engine; see note below). |
| `exit` | (none) | `"You can't exit that."` by default (no automatic "exit" == "go out" mapping in the Python engine; see note below). |
| `wait` | `z` | `"Time passes."` Always allowed, even in the dark. |
| `again` | `g` | Repeats the last typed command line. |
| `attack` | `hit`, `kill`, `fight` | `"Violence isn't the answer here."` -- always a no-op unless overridden by a rule. |
| `talk` | `speak` | `"There's no reply."` (also covers `ask`/`tell`, which share this same default response). |
| `ask` | (own entry, also routed to the "no reply" response) | See `talk`. |
| `tell` | (own entry, also routed to the "no reply" response) | See `talk`. |
| `give` | (none) | `"There's no one here to give that to."` |

**Engine-vs-browser parity:** the browser runtime (`engine/web/template.html`) matches the Python
reference engine (`engine.py`) exactly for `enter` and `exit` -- both treat them as ordinary
single-word verbs with the no-op defaults above (`"You can't enter the X."` / `"You can't exit
that."`), and neither maps `enter <direction>` or bare `exit`/`out` onto movement automatically.
Likewise, neither runtime special-cases multi-word verb phrases like "pick up" -- `take` already
carries `pick` as a single-word synonym (see the table above), so `pick lamp` works in both
runtimes but `pick up lamp` parses as verb `pick` + noun phrase `up lamp` in both (and will fail
to resolve "up lamp" as an object) -- this is intentional parity, not a bug in either engine. If
your game wants `enter <room>` or `exit` to move, or wants a true multi-word "pick up" verb,
write a rule for it in the world JSON (or extend `vocabulary.verbs`) so both runtimes behave
identically, since a single world JSON must play the same in both. See
`engine/web/parity_test.mjs` for the automated check that keeps the two runtimes in lockstep.

## Meta verbs

Handled directly by `Engine._handle_meta()` / `run_loop()` in `play.py`, **before** rules or
default handlers ever run, and not rule-overridable.

| Verb | Behavior |
|---|---|
| `save` | (CLI only, via `play.py`, not `engine.py` itself) `save [path]` writes a JSON snapshot to the given path or the default save path. |
| `load` / `restore` | (CLI only, via `play.py`) reads a JSON snapshot back and restores full state. |
| `undo` | Pops the last pushed state snapshot (up to 10 levels) and restores it; `"Nothing to undo."` if the stack is empty. Every command pushes an undo snapshot before it runs. |
| `restart` | Raises `GameOver("restart")`, which `play.py`'s outer loop catches and reloads the world fresh. |
| `quit` / `q` | Raises `GameOver("quit")`, which ends the session with `"Goodbye."` |
| `score` | Prints `"You have scored X out of Y points in Z turns."` |
| `help` | Prints a one-line summary of the standard command set. |
| `verbose` | Turns on full room descriptions every visit. |
| `brief` | Turns off repeat full descriptions (only shown on first visit). |

Note: `save`/`load` as file-based commands are a `play.py` convenience layered on top of
`engine.py` (which only exposes `save_game()`/`load_game()` as library functions) -- the browser
runtime implements its own `save`/`load` against `localStorage` instead of a file, so the two
runtimes' persistence mechanisms are not directly interchangeable.
