# Authoring workflow

The step-by-step process for building a new game with this skill, from a bare premise to a
delivered, verified world file.

## 1. Elicit the premise

Ask (or infer from context) the setting, tone, rough length (how many rooms / how many
puzzles), and the win condition. A short game might be 3-5 rooms and one central puzzle chain
(like the bundled `the-cellar` example: kitchen -> cellar -> vault, one key puzzle, one
placement-based win). Confirm scope before writing any JSON.

## 2. Design on paper first

Before touching the world JSON:

- **Room map**: sketch every room and its exits (including any door-gated or hidden ones) so
  the geography is internally consistent (see `design-principles.md` on consistent mapping).
- **Object list**: every object that will exist, where it starts, and which flags it needs
  (portable? container? light source? locked, and with which key?).
- **Puzzle dependency graph**: for every puzzle, write down exactly what state must be true
  before it can be solved, and what state becomes true once it is. Chain these to prove the
  game is **completable by construction** -- not "probably possible," but a graph you can trace
  start-to-finish through explicit prerequisites. This is what a walkthrough command list will
  later encode and prove mechanically.

## 3. Generate the world JSON

Start from `templates/world.template.json` (a minimal valid scaffold) and `templates/stubs.md`
(copy-paste snippets for rooms, objects of every flag combination, and rules of every trigger
type). Consult `references/world-schema.md` for exact field semantics and
`references/rules-system.md` for the triggers/conditions/effects mini-language while writing
puzzle rules. Write the full room/object/rule set matching the design from step 2.

## 4. Verify: walkthrough + fuzz

This is the mandatory proof step -- **do not skip it and do not treat it as optional polish.**

1. Write `<yourgame>.walkthrough.txt`: the exact winning command sequence, one command per
   line, `#` comments allowed, matching the puzzle dependency graph from step 2.
2. Run it:
   ```
   python engine/walkthrough_runner.py path/to/yourgame.json path/to/yourgame.walkthrough.txt
   ```
   It must print `PASS: walkthrough completed in N turns, score S/max.` If it prints `FAIL`, the
   output includes a full transcript of every command and its response -- use that to find
   exactly where the game diverged from the intended path (a wrong object id, a rule that never
   fires, a condition gated on an undeclared flag, etc.) and fix the world JSON, not the runner.
3. Fuzz nonsense input: play the game manually with `python engine/play.py path/to/yourgame.json`
   and deliberately throw unknown verbs, unknown nouns, empty input, and commands referencing
   objects not currently in scope. Confirm every case gets a friendly message
   (`"I don't know how to '...'."`, `"You can't see any such thing."`, etc.) and never a raw
   traceback or a frozen session. `play.py` and `walkthrough_runner.py` both have a catch-all
   safety net around command execution, but that net is a last resort -- content bugs should be
   fixed at the source, not relied on to be silently swallowed.
4. Repeat steps 3 (design fix) and this step until both the walkthrough and the fuzz pass clean.

## 5. Polish prose

Once the game is mechanically sound:
- Add or improve `examine` text for every object mentioned in any room/object description (see
  "Examinability" in `design-principles.md`).
- Tune synonyms and adjectives so natural phrasings resolve correctly (test the exact wordings a
  player is likely to try).
- Re-read against the fairness/cluing/cruelty-scale guidance in `design-principles.md`.

## 6. Optional: export to HTML

If a standalone browser copy is wanted, copy `engine/web/template.html` to a new file and paste
the finished world JSON into its `<script id="world" type="application/json">` block (see
`SKILL.md` for the exact mechanism). Note the browser runtime is a separate JS reimplementation
of the rules model (see `rules-system.md`'s warning about `hooks.py` not running there) -- if the
game used `hooks.py` for anything load-bearing, either move that logic into declarative rules
first, or treat the HTML export as a lesser, Python-hooks-free version of the game.

## Hard rule

**Do not deliver a game until its walkthrough passes.** A `PASS` line from
`walkthrough_runner.py`, obtained by actually running it (not assumed), is the minimum bar for
calling a game done.
