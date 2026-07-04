---
name: skill-clone-forge
description: >-
  Reverse-engineer and rebuild any existing app or game as an original clone
  with equal or greater quality, equal or greater functionality, and a modular
  data-driven architecture that makes later improvements cheap. USE THIS SKILL
  whenever the user says clone, "clone this game/app", recreate, reimplement,
  remake, "rebuild X better", "make my own X", spiritual successor, "port X to
  [platform]", reverse-engineer, feature parity, or references a target like
  "a Beach Head 2000 clone" / "a Mega Man X clone" / "like Vampire Survivors
  but..." / "my own version of 2048". Also trigger for feature-parity rebuilds,
  "make it better than the original" requests, and "rebuild this legacy
  app/tool" asks — even when the word clone never appears. Drives a 6-phase
  pipeline (IP gate → deconstruction → parity+improvement spec → modular
  architecture → incremental build → proof gate) and 14 hard-won rules that
  keep clones IP-clean, modular, and at parity-or-better instead of shipping an
  inferior knockoff. Works for both GAMES and APPS — rubrics have a variant for
  each. Prefer this over improvising: an unstructured clone attempt ships worse
  feel than the original and hardcodes everything you'll want to tune later.
metadata:
  version: 1.0.0
---

# Clone Forge

**Confluence sources for auto-sync:**

| Source Page | Page ID | Content |
|-------------|---------|---------|
| Project Logs hub | 98494 | Clone project logs live here |
| (add clone session-lessons pages as they accrue) | — | — |

**Last synced:** <date> | **Source version:** clone-forge v1.0

Disciplined pipeline for rebuilding an existing app or game as an **original,
legally clean clone** that matches or beats the target. Grew out of shipping
real clones (Browser Generals ← C&C Generals, Beachhead ← Beach Head 2000,
Bounty Hunter X ← Mega Man X): every rule below exists because the naive
approach failed first. Three promises, all **operationalized — never vibes**:

1. **Equal-or-greater quality** → scored against the rubric in
   [references/quality-and-parity.md](references/quality-and-parity.md)
   (perf budget, feedback density, accessibility, polish).
2. **Equal-or-greater functionality** → a parity checklist: every target
   feature mapped to a build task and ticked, plus explicit additions.
3. **Modular for improvement** → data-driven separation + an extension-point
   registry that is **exercised at validation** (add a level/enemy/screen
   through data only), so modularity is demonstrated, not claimed.

## Reference files — read when needed

- [references/deconstruction-method.md](references/deconstruction-method.md) —
  read at Phase 1: how to reverse-analyze a target; separate GAME and APP
  teardown checklists.
- [references/modular-architecture.md](references/modular-architecture.md) —
  read at Phase 3: data-driven patterns, module contracts, the extension-point
  registry, and the stack-picker.
- [references/quality-and-parity.md](references/quality-and-parity.md) — read
  at Phase 2 (to set the bar) and Phase 5 (to score against it): quality/feel
  rubric (game + app variants), parity checklist mechanics, validation gates.

Templates to instantiate (copy into the repo, don't write from scratch):
[assets/CLONE_PLAN.template.md](assets/CLONE_PLAN.template.md),
[assets/DECONSTRUCTION.template.md](assets/DECONSTRUCTION.template.md),
[assets/ARCHITECTURE.template.md](assets/ARCHITECTURE.template.md).

## Project rails (set up before Phase 1)

- **Repo lives OFF OneDrive:** `C:\Claude\Projects\Active\<Project>\`.
  OneDrive has eaten canonical docs before (June 2026). `git init` at repo
  root; commit per milestone; `git bundle create <project>.bundle --all` at
  each phase gate for durability.
- **`CLONE_PLAN.md` at repo root is canonical.** Keep a Confluence survivor
  copy under the Project Logs hub (ancestor `98494`). Repo wins if they
  disagree.
- **Model tiering — tag every phase:** Phases 0–3 and the Phase 5 judgment are
  **Fable/Opus** (plan/architect/judge). Phase 4 build is **Sonnet agents with
  an Opus architect-reviewer**. Never trust an executor's self-report — the
  judge re-runs the checks (Beachhead: 3 real bugs survived executor
  self-report; Bounty Hunter X: judge caught constants tampering).
- Use TaskCreate — a clone is always a ≥3-step build.

## The 6-phase pipeline

### Phase 0 — IP & scope gate  *(Fable/Opus — NEVER skip, always first)*

Split the target into two layers before anything else:

- **Cloneable layer** (mechanics, rules, core loop, systems, UX patterns,
  information architecture, feel/juice) — game mechanics and functional design
  are not copyrightable. Clone freely.
- **Protected layer** (name, logos, art, music, characters, story/dialogue,
  distinctive proprietary assets, trademarked terms) — reproduce **none** of
  it. Generate original everything-else.

Check the license on any reference source code before drawing from it —
"decompiled source on GitHub" is not a license. If the user asks to reproduce
protected assets or ship under a trademarked name, **stop and flag**; offer
the mechanics-clone-with-original-skin path instead (that's what this skill
builds anyway).

**Output: a one-paragraph clone charter** — what we clone, what we replace
with originals, and the improvement thesis (the reason this clone deserves to
exist).

### Phase 1 — Deconstruct  *(Fable/Opus)*

Study the target: play it, read teardowns, watch footage, read docs. Read
[references/deconstruction-method.md](references/deconstruction-method.md)
and fill [assets/DECONSTRUCTION.template.md](assets/DECONSTRUCTION.template.md).
Cover: core loop; mechanics inventory; systems (progression, economy,
difficulty, state); UX/UI patterns + information architecture; content
structure; **feel & feedback** (game: timing, easing, audio, particles,
screen-shake; app: responsiveness, micro-interactions, empty/error states);
tech guess (platform, likely architecture, data shapes).

Name two things explicitly: the **fun/value core** (the ~20% that makes the
target work) and the **friction/dated seams** (what you'll improve — this
feeds the improvement thesis). **Output: `DECONSTRUCTION.md`.**

### Phase 2 — Parity + improvement spec  *(Fable/Opus)*

- Build the **feature-parity checklist**: every target feature → a build task
  with a tier tag (`v1-slice` / `v1` / `v2` / `cut`). A cut is a decision, not
  an omission — record why.
- Operationalize the **improvement thesis**: what the clone does *measurably*
  better, plus explicit additions.
- Set the **quality bar** concretely via the rubric in quality-and-parity.md:
  perf budget (game: 60fps on mid hardware; app: interactive < 2s), feedback
  density, accessibility floor, friction removed.
- Cut scope to a **vertical slice** for v1.

**Output: `CLONE_PLAN.md`** from the template (objective · parity checklist ·
improvement thesis · quality bar · phased scope with tier tags · stack ·
risks). Publish the survivor copy to Confluence.

### Phase 3 — Modular architecture  *(Fable/Opus — the signature phase)*

Read [references/modular-architecture.md](references/modular-architecture.md).
Enforce three things:

1. **Data-driven separation.** All tunable content/config in data (JSON / JS
   config objects / Godot resources); logic reads data; nothing a designer
   would want to tune is hardcoded. Design the data schema **before** the
   systems — the schema is the contract.
2. **Module boundaries.** Each system is a swappable module with an explicit
   input/output contract, written down.
3. **Extension-point registry.** Name every seam where future improvements
   plug in (new level = new data entry; new enemy = data + optional behavior
   module; new mode = new mode module) and document each in the registry
   table. Phase 5 will exercise one — design them to survive that test.

Pick the stack via the stack-picker. Defaults: **single-file HTML5 + vanilla
JS** (no build step) for web games/apps; **Godot 4 / GDScript** for anything
targeting mobile from a Windows-only setup. No heavy framework unless the
target genuinely demands it. **Output: `ARCHITECTURE.md`** (module map + data
schema + extension-point registry).

### Phase 4 — Incremental build  *(Sonnet build, Opus architect-review)*

- **Vertical slice first:** the smallest end-to-end version of the core loop,
  fully wired (input → logic → feedback → state), vector/placeholder art.
  Prove the fun/value before breadth — if the slice isn't fun/useful, stop and
  fix the loop, not the content.
- Then build **module by module against the parity checklist**, ticking as
  you go.
- **Smoke-test cadence:** run and verify after every module; never declare a
  module done without running it. Mirror the 17/17 ×3 cadence — automated
  checks run three times where flakiness is possible, plus a manual smoke
  test always.
- Commit per milestone; keep `CLONE_PLAN.md` and the Confluence survivor copy
  current; refresh the git bundle at each phase gate.

### Phase 5 — Parity / quality / modularity gate  *(Fable/Opus judge — not the builder)*

Read quality-and-parity.md §Validation. Four checks, all evidence-backed:

1. **Functionality proven:** walk the parity checklist; every non-cut item
   ticked with a how-verified note.
2. **Quality proven:** score the rubric; A/B the feel against the target
   side-by-side where possible. Parity-with-worse-feel = FAIL.
3. **Modularity proven:** exercise one extension point — add a trivial
   level/enemy/screen/mode **through data only**, zero logic edits. If it
   needs a code change, the registry lied; fix the seam.
4. **Improvement thesis shipped:** the measurable "better" is demonstrable.

**Output: a validation report** (in-repo + project log under `98494`). No
gate, no "done."

## Hard-Won Rules

### IP & scope

1. **Clone mechanics, not IP.** Original name, art, audio, story — always.
   Reproducing protected assets is legally toxic and creatively lazy; it's the
   fast path to a takedown of something you spent weeks building.
2. **The IP gate runs before any other work, every time.** Discovering a
   trademark problem at ship time forfeits the whole naming/branding layer —
   a 5-minute Phase 0 versus days of rework.
3. **Check the license on reference source before reading it.** Untangling
   "how much did we derive from that GPL decompile" after the fact is
   impossible; know the answer before you look.

### Deconstruction & spec

4. **The fun core is a small fraction of the target — find it first, protect
   it.** Most of a polished product is incidental; identify the ~20% that
   carries it and guard it through every scope cut. Cut anything else first.
5. **Parity is a checklist, not a vibe.** If it isn't on the checklist and
   ticked, it doesn't count as shipped. "Feels complete" has missed shipped
   features on every clone that skipped the list.
6. **Deconstruct from the real target, not from memory.** Play it / drive it
   the same day you write `DECONSTRUCTION.md`. Building from a remembered
   version means cloning a game that doesn't exist — and parity against a
   phantom can't be verified.

### Architecture & modularity

7. **Modular and data-driven from line one — never retrofit.** Retrofitting
   modularity onto a hardcoded prototype costs more than the prototype did;
   the data schema is the contract, design it before the systems.
8. **Extension points must be exercised, not assumed.** Prove modularity by
   adding something new through data only; an untested seam is a guess, and
   guessed seams are always welded shut somewhere.
9. **Match the platform to the house stack.** Single-file HTML5 for web;
   Godot/GDScript for Windows→mobile. A framework the target doesn't need is
   pure carrying cost — every future improvement pays it.

### Build & verification

10. **Vertical slice before breadth.** Prove the core loop end-to-end before
    building any content. If the slice isn't fun, more features won't save
    it — they'll just make the failure more expensive.
11. **Nothing is done until it's been run.** Smoke-test every module; 17/17 ×3
    cadence. A green build is not a working build — Beachhead shipped 3 real
    bugs past an executor that reported success on all of them.
12. **The judge is never the builder.** Executors self-report success; verify
    with a different (higher-tier) model against raw artifacts, not agent
    prose. Spot-check outputs directly before planning on any claim.

### Quality & durability

13. **Feel is a feature — budget it explicitly.** Juice/polish (game) or
    micro-interactions and empty/error states (app) get their own line in the
    plan. At feature parity, a clone with worse feel reads as strictly
    inferior, and "we'll polish later" is how it ships that way.
14. **Repos live off OneDrive; bundle + survivor-copy for durability.** Git at
    `C:\Claude\Projects\Active\`, `git bundle` at each gate, Confluence
    survivor copy under `98494`. OneDrive has eaten canonical docs before;
    repo is canonical when they disagree.

## Pre-Build Checklist

Before writing any product code, confirm:

- [ ] Phase 0 charter written; protected layer listed; no trademarked name in use
- [ ] Reference-source licenses checked (or no reference source used)
- [ ] `DECONSTRUCTION.md` written **from the live target**, fun core named
- [ ] `CLONE_PLAN.md` at repo root: parity checklist tiered, improvement
      thesis measurable, quality bar numeric
- [ ] `ARCHITECTURE.md`: data schema drafted, module contracts written,
      extension-point registry has ≥3 named seams
- [ ] Repo at `C:\Claude\Projects\Active\<Project>\`, git initialized,
      Confluence survivor copy created under `98494`
- [ ] Phases tagged with model tier; TaskCreate list exists

## Post-Build Validation

Before calling the clone done:

- [ ] Every non-cut parity item ticked with a how-verified note
- [ ] Quality rubric scored; perf budget met with numbers, not impressions
- [ ] Side-by-side feel A/B against the target done (or explicitly waived
      with reason)
- [ ] One extension point exercised through **data only** — zero logic edits
- [ ] Improvement thesis demonstrated, not asserted
- [ ] 17/17 ×3: automated checks green three consecutive runs + manual smoke
      test passed
- [ ] Judge (non-builder, top-tier model) verified against raw artifacts
- [ ] Milestone commits + fresh git bundle + Confluence survivor copy current
- [ ] Validation report written; project log under `98494` updated
