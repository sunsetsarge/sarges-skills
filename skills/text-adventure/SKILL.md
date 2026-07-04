---
name: text-adventure
description: Designs, builds, tests, and ships parser-based text adventures / interactive fiction in the Zork tradition -- rooms, objects, inventory, a natural-language verb-noun parser, puzzles, light/dark mechanics, and win/lose conditions. Fires on requests for a text adventure, interactive fiction, IF game, text-based RPG, Zork or Zork-like game, parser game, text adventure engine, "make me a text game", a dungeon crawl with typed commands, MUD-like single-player games, or room-and-inventory games. Covers design, engine mechanics, content authoring, and automated win-state testing for parser games -- NOT choice-based hypertext like Twine.
---

# text-adventure

## 1. What this builds

A data-driven parser-based text adventure: one JSON "world" document (rooms, objects, exits,
flags, rules, vocabulary) drives a stdlib-only Python engine (`engine/engine.py`) for
authoring and playtesting, plus an optional single-file HTML export for playing in a browser.
The world JSON is the single source of truth -- no game content is hard-coded into the engine.

## 2. When to use / not use

Use for: Zork-likes, room-and-inventory games, MUD-like single-player games, "type commands to
explore a dungeon/house/ship", puzzle-box IF, anything where the player types free-text verbs
(`take lamp`, `unlock door with key`, `put crown on altar`).

Do NOT use for choice-based hypertext (Twine, "click a link to pick your path", visual novels
with branching menus instead of a typed parser) -- that's a different genre with different
tooling; steer those requests elsewhere.

## 3. Authoring workflow at a glance

1. Elicit premise, setting, tone, and rough size (rooms/puzzles) and the win condition.
2. Design on paper: room map, object list, and a puzzle-dependency graph so the game is
   provably completable by construction (not by luck).
3. Write the world JSON (start from `templates/world.template.json` + `templates/stubs.md`).
4. Verify: run the engine and `walkthrough_runner.py` against a command list that should win;
   fuzz nonsense input; fix until both are clean.
5. Polish prose (examine text for every mentioned object, tune synonyms).
6. Optionally export to a single-file HTML page for browser play.

See `references/authoring-workflow.md` for the full step-by-step version of this process.

## 4. Architecture at a glance

- **JSON is truth.** Every room, object, exit, flag, verb synonym, and puzzle lives in the
  world JSON. The engine never contains game-specific logic.
- **Engines are thin.** `engine/engine.py` implements only mechanics: world model, parser,
  default verb handlers, the rules evaluator, and meta systems (score/turns/save/undo/rank).
- **Puzzles are declarative.** Puzzle logic is expressed as rules (trigger -> conditions ->
  effects) in the world JSON, not as engine code. A Python-only `hooks.py` escape hatch exists
  for logic too dynamic for rules, but it does not run in the HTML export (see
  `references/rules-system.md`).

## 5. Non-negotiables

- **A game must be proven completable before delivery.** Run `walkthrough_runner.py` with a
  winning command sequence and confirm it prints `PASS`. Do not deliver a game whose
  walkthrough has not been run and does not pass.
- **No unwarned softlocks.** Never let a required item become permanently unobtainable, or an
  exit seal permanently, without a clear in-world warning or an alternate path.
- **Unknown input must never crash.** Unrecognized verbs/nouns get a friendly error
  ("I don't know how to '...'.", "You can't see any such thing."), never a stack trace or a
  frozen game. Both `play.py` and `walkthrough_runner.py` also catch unexpected exceptions as a
  last-resort safety net.
- **Everything mentioned in prose must be examinable.** If a room description or another
  object's text names something, it must exist as an object with `examine` text (or a rule that
  handles it) -- not a dead reference.

## 6. Where to look

- `references/world-schema.md` -- every field of `meta`/`rooms`/`objects`/`rules`/`vocabulary`/
  `flags`, location forms, door-gated exits, ranks. Read when writing or debugging a world JSON.
- `references/parser-design.md` -- tokenizing, vocabulary/synonyms, noun resolution, scope,
  disambiguation, pronouns, chaining, error messages. Read when a command isn't parsing the way
  you expect.
- `references/standard-verbs.md` -- the canonical verb list, synonyms, and default behavior for
  each. Read when deciding which verbs a puzzle needs to override.
- `references/rules-system.md` -- the triggers/conditions/effects mini-language, evaluation
  order, and the `hooks.py` escape hatch. Read when authoring any puzzle.
- `references/design-principles.md` -- IF craft: fair puzzles, cluing, cruelty scale, pacing.
  Read before/while designing the map and puzzle graph.
- `references/authoring-workflow.md` -- the full step-by-step build process. Read at the start
  of a new game and again before declaring it done.

## Running it

```
python engine/play.py examples/the-cellar.json
python engine/walkthrough_runner.py examples/the-cellar.json examples/the-cellar.walkthrough.txt
```

`play.py` is stdlib-only (works with a bare `python`). `walkthrough_runner.py` feeds a command
list from a `.txt` file (one command per line, `#` comments allowed) and exits 0 with `PASS`
only if the world reaches `win == True`; otherwise it exits 1 with `FAIL` and a full transcript.

**HTML export:** copy `engine/web/template.html` to a new file, then paste the finished world
JSON into the `<script id="world" type="application/json">` block near the top of the file
(replacing the placeholder `{}`), and save. The exported file is self-contained (no build step,
no CDN) -- opening it in a browser loads the embedded world directly. If that script tag is left
empty, the page instead shows a file-picker/paste box so a world can be loaded manually. The
HTML runtime reimplements the same rooms/objects/rules model in JavaScript so it can run
standalone; it does not execute Python `hooks.py` (see `references/rules-system.md` for what
that means for puzzles that use hooks).

**Cross-runtime check:** `node engine/web/parity_test.mjs` runs `examples/the-cellar.json`'s
walkthrough through the extracted browser engine-core under Node and confirms it reaches the
same win/score/turns result as `walkthrough_runner.py` gets from the Python engine. Run it after
touching either runtime's rules/effects/parser logic, alongside `walkthrough_runner.py`, before
calling a game (or an engine change) done.
