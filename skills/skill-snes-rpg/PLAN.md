# PLAN — skill-snes-rpg Optimization (Fable-authored, Opus/Sonnet-executed)

Author: Fable 5 session, 2026-07-11. Executor: any later Opus or Sonnet session — no Fable
required. Read STATE.md first; execute phases in order; each phase ends with its acceptance
criteria verified and a STATE.md update (session-handoff wrap).

Method: anthropic-skills:skill-creator loop (draft → subagent test runs → eval viewer → human
review → revise), adapted to an EXISTING skill (baseline = pre-edit snapshot, not no-skill).

## Tier routing (binding)

| Role | Model | Used for |
|---|---|---|
| Planner/judge | Opus (session top model) | Phase gates, grading judgments, rule-list revisions |
| Executor | Sonnet subagents (`model: "sonnet"`) | All file edits, test-run builds, script writing |
| Grinder | Haiku subagents (`model: "haiku"`) | Mechanical checks (grep sweeps, line counts, JSON lint) |

Standing rule (memory: verify-subagent-claims): no executor claim counts without an artifact
(file diff, script output, screenshot). "All green" prose = UNVERIFIED.

## Audit findings (2026-07-11, Fable) — what this plan fixes

Confidence labels: [K]=known/verified this session, [I]=inferred, [G]=guessed.

- **D1 [K] The skill's examples violate its own validation contract.** `reference/data-schemas.md`
  and `battle-system.md` examples reference spell ids `ember_storm`, `enrage_self`, `tide_surge`
  that are defined nowhere, while the load-time contract in the same file declares dangling refs
  a fatal error. A builder that copies the examples ships data its own validator rejects.
- **D2 [K] No element registry.** Schemas use `$ref: "elements.id"` but elements are not one of
  the six data files and have no canonical definition anywhere — the cross-reference pass as
  specified cannot resolve them. Data-model hole.
- **D3 [K] Zero live builds.** All 25 rules and the workflow are untested by an actual build
  session. The demo proves only the battle loop. This is the largest risk: plausible-but-wrong
  guidance survives until someone builds with it.
- **D4 [I] Missing bundled script.** Every build session will hand-write the ~60-line data
  validator the skill mandates. skill-creator guidance: repeated work across runs → bundle a
  script. Ship `scripts/validate_data.py`.
- **D5 [K] Trigger description never empirically tested.** "Triggers on 10+ phrasings" was
  asserted, not measured. skill-creator's `run_loop.py` measures it.
- **D6 [K] No eval harness.** No `evals/evals.json`, no assertions, no benchmark — nothing to
  detect regressions when the skill is edited later.

## Phase 1 — Fix known defects (Sonnet executes, Opus spot-checks)

1. Resolve **D2**: add an `elements` block to `reference/data-schemas.md` — either a 7th data
   file `elements.json` (id, name, opposing element) or a fixed enum in the schema conventions
   section. Executor picks whichever keeps SKILL.md's "six data files" language consistent
   (renumber or enum — state the decision in STATE.md DECISIONS).
2. Resolve **D1**: add `ember_storm`, `enrage_self`, `tide_surge` to the spells example (3 short
   entries) so every referenced id resolves. Then grep-audit ALL example ids both directions.
3. Resolve **D4**: write `scripts/validate_data.py` (stdlib-only, Python 3.10-safe for
   `C:\AI-Shared\python.exe`): structural checks per schema + cross-ref pass + sanity pass
   exactly as the "Load-time validation contract" section specifies; exit non-zero with
   file/path/reason on failure. Include a self-test mode that validates the doc's own examples
   (extract fenced JSON blocks). Reference it from SKILL.md rule 14 and the workflow.
4. Keep SKILL.md under 500 lines after edits.

**Acceptance:** `validate_data.py --self-test` passes against the fixed examples AND fails
loudly when an id is deliberately broken (show both outputs); grep sweep shows zero dangling
ids; SKILL.md line count < 500; IP grep still zero hits. Bump skill `metadata.version` to 1.1.

## Phase 2 — Eval harness + baseline benchmark (Sonnet builds, Opus grades)

1. Snapshot the pre-Phase-1 skill: `git show d640fd6` tree → `../skill-snes-rpg-workspace/skill-snapshot/`
   (workspace is a SIBLING of the skill dir, per skill-creator; NOT inside the repo).
2. Write `evals/evals.json` with 3 test prompts (real-user shaped), e.g.:
   - E1 "build me a small retro JRPG battle demo — 2 heroes, a boss with two phases, ATB bars"
   - E2 "make a 16-bit RPG vertical slice: one town with a shop and inn, one 3-floor dungeon
     with a boss, random encounters, save at the inn" (the big one)
   - E3 "add an equip-to-learn magic system and an elemental weakness chart to this battle demo"
     (input file: the skill's own atb-loop-demo.html)
3. Assertions per eval, objectively checkable, e.g. E2: data validated at load (break a JSON id
   → visible error screen); menu open 10s → zero gauge movement; 4–8 encounter-free steps after
   battle; save→reload round-trip intact; zero franchise proper nouns (grep). Derive the rest
   from SKILL.md's own Post-Build Validation list — the skill grades against its own checklist.
4. Spawn with-skill AND old-skill (snapshot) runs in the same turn, Sonnet executors,
   **executor prompts must forbid the Agent tool** (memory: delegation-spiral lesson). Capture
   timing.json per run from task notifications.
5. Grade (Opus, per `agents/grader.md`), aggregate benchmark, generate the eval viewer with
   `generate_review.py` for Blaine BEFORE self-analyzing. **Windows note (memory):** run
   skill-creator scripts with `C:\AI-Shared\python.exe` (3.10) and apply the two known Windows
   patches to its scripts before first use.

**Acceptance:** benchmark.json + viewer HTML exist; every assertion graded with evidence paths;
Blaine has been given the viewer link. Gate to Phase 3 = Blaine's feedback.json (or explicit
"skip review, proceed").

## Phase 3 — Revise from evidence (Opus judges, Sonnet edits)

1. Read transcripts, not just outputs: where did builders ignore/misread the skill? Where did
   they all hand-write the same helper (→ bundle it)? Which of the 25 rules did no run ever
   need (→ candidates to cut — keep SKILL.md lean)?
2. Apply revisions (Sonnet), rerun the eval set into iteration-2 with `--previous-workspace`,
   regrade. Repeat max twice; stop when assertion pass-rate stops improving or Blaine is happy.

**Acceptance:** iteration-2 pass rate ≥ iteration-1 on the same assertions, with the benchmark
delta shown; any removed/changed rule justified in one line in STATE.md DECISIONS.

## Phase 4 — Description trigger optimization (Sonnet runs the loop, Opus reviews)

1. Generate 20 trigger queries (8–10 should-trigger incl. mechanics-only phrasings; 8–10 tricky
   near-misses: action-platformer asks that belong to snes-action-platformer, RPG Maker MV asks
   that belong to the rpgmaker-mv MCP, text-RPG asks that belong to text-adventure, generic
   browser-game asks that belong to browser-game-builder). Blaine reviews via the
   `assets/eval_review.html` flow.
2. Run `scripts/run_loop.py` (background, `--max-iterations 5`, session model id). Apply
   `best_description` only if held-out test score beats the current description's.

**Acceptance:** before/after descriptions + train/test scores reported; SKILL.md updated only on
a measured win; catalog page NOT touched (description text lives in the repo only).

## Phase 5 — Ship (Opus)

Commit all changes to sarges-skills as `skill-snes-rpg v1.1` with a body listing D1–D6
resolutions and benchmark deltas. **BLAINE GATE: push.** Update Confluence build-log page
80969731 (append a v1.1 entry — full-body replace, versionMessage, verify live) and the Skills
Catalog row version cell. session-handoff wrap.

## Budget & guardrails

- Expected shape: Phase 1 ≈ one Sonnet session; Phase 2–3 are the expensive ones (3 evals × 2
  configs × 2 iterations ≈ 12 subagent builds) — run builds `model: "sonnet"`, never Opus.
- Workspace stays OUTSIDE the repo (`C:\Claude\sarges-skills\skills\skill-snes-rpg-workspace\`
  is WRONG — that's inside `skills/`; use `C:\Claude\skill-snes-rpg-workspace\`). Nothing from
  the workspace, STATE.md, or PLAN.md gets committed to the public repo.
- No franchise IP may enter via eval prompts or executor output — E-prompts phrase the genre
  generically; the IP grep is a standing assertion in every iteration.
- If any phase invalidates a SKILL.md claim (e.g., a rule proven wrong), fixing the skill beats
  preserving the plan — note the deviation in STATE.md.
