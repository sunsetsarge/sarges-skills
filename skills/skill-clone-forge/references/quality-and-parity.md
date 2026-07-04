# Quality & Parity (Phases 2 and 5)

"Equal or greater" is a claim about measurements, not impressions. This file
defines the rubric that sets the bar (Phase 2) and the gates that prove it
(Phase 5). Use the GAME or APP variant as appropriate; hybrids score both.

## The parity checklist (functionality)

Built in Phase 2 from `DECONSTRUCTION.md`; lives in `CLONE_PLAN.md`.

- **One row per target feature** — every verb, screen, system, and setting
  from the teardown. If the teardown found it, the checklist has it.
- Columns: `Feature | Tier | Build task | Verified how | ✓`
- **Tiers:** `v1-slice` (vertical slice), `v1` (parity release), `v2`
  (post-parity), `cut` (deliberately dropped — with a reason; a cut is a
  decision, not an omission).
- **Additions** (improvement-thesis features) go in a separate section so
  parity and betterment are never conflated.
- At Phase 5, every non-cut `v1` row must be ticked **with a how-verified
  note** ("played level 3, all spawn waves fired" / "created, edited,
  deleted, undid"). An unticked row = not shipped, whatever it feels like.

## Quality/feel rubric

Score each line 0–2 (0 = below target, 1 = parity, 2 = better than target).
**Gate: no 0s on any line; the improvement thesis needs 2s where it claims
them.** Set the numeric budgets in Phase 2 — defaults below are the floor.

### GAME variant

| Line | Measure | Default budget |
|---|---|---|
| Frame rate | Sustained fps in worst-case scene (max entities on screen) | 60fps on mid hardware; no dips below 50 |
| Load/boot | Double-click → playable | < 3s |
| Input latency | Input → visible response | Next frame; no perceptible lag |
| Feedback density | Every player-relevant event (hit, pickup, death, level-up...) has ≥2 channels of feedback (visual + audio; +haptic/shake where apt) | No silent events on the core loop |
| Feel fidelity | Core-loop timings within tolerance of the teardown's measured numbers (or deliberately improved — note which) | Matches DECONSTRUCTION.md figures |
| Readability | Action parseable at a glance: contrast, silhouette, telegraphs before damage | Every damage source is telegraphed |
| Difficulty curve | Ramp matches the teardown's structure; first-session completion of the opening chunk | New player survives the tutorialized part |
| Accessibility floor | Pause anywhere, remappable/documented controls, no flashing strobes, colorblind-safe critical cues, audio not required to play | All five |
| Polish | Title, game over, restart loop, settings persist, no debug text, window/scale handling | All present |

### APP variant

| Line | Measure | Default budget |
|---|---|---|
| Time-to-interactive | Launch → usable | < 2s |
| Action feedback | Every action confirms within 100ms (optimistic UI or progress state); nothing "just happens silently" | 100% of actions |
| Task efficiency | Clicks/keystrokes on the top-5 tasks vs. the teardown's measured counts | ≤ target on all 5 (this is a natural improvement-thesis line) |
| Empty states | Every list/screen has a designed empty state that tells the user what to do | No blank screens |
| Error states | Every failure path has a human-readable message and a recovery action | No raw errors, no dead ends |
| Undo/confirm | Destructive actions are undoable or confirmed | 100% |
| Data safety | No data loss on crash/refresh mid-task; save/persist verified | Kill it mid-edit, nothing lost |
| Accessibility floor | Full keyboard path for core tasks, visible focus, labeled controls, WCAG AA contrast | All four |
| Responsiveness/layout | Works at the target's supported sizes (and mobile width if web) | No broken layouts |
| Polish | Consistent spacing/typography tokens, loading skeletons, sensible defaults, settings persist | All present |

### The feel A/B (both variants)

Run the target and the clone **side by side** and perform the same 5-minute
core task/loop in each, twice. Note every moment the clone feels worse and
file each as a fix or an accepted, written trade-off. If the target can't be
run, A/B against the recorded footage from Phase 1. Waiving the A/B requires
a written reason in the validation report. At feature parity, worse feel
reads as strictly inferior — this check is not optional because the rubric
"passed."

## Phase 5 gates (all four, evidence-backed)

1. **Parity gate** — checklist walk, every non-cut row ticked with evidence.
2. **Quality gate** — rubric scored with the measured numbers; feel A/B done.
3. **Modularity gate** — exercise ≥1 extension point from the registry by
   adding a trivial level/enemy/screen/mode **through data only** (`git diff`
   shows data files only — that's the proof). If logic changed, the seam is
   broken: fix it, don't excuse it.
4. **Improvement gate** — each improvement-thesis claim demonstrated with its
   measurement (before/after numbers or side-by-side).

**Judge ≠ builder.** The gate is run by the top-tier model against raw
artifacts (run the game, run the tests, read the diff) — never against the
builder's self-report. 17/17 ×3: automated checks pass three consecutive
runs; a manual smoke test happens regardless of how green CI is.

**Output: validation report** in-repo (scores, evidence links, A/B notes,
the modularity-proof diff hash, open trade-offs) + project log under
Confluence `98494`.

## Failure playbook

- Rubric line scores 0 → fix before ship; the line's budget was set in Phase
  2 precisely so this isn't negotiable at Phase 5.
- Feel A/B loses badly despite rubric parity → the teardown missed a feel
  variable; go measure the target again (frame-scrub), update
  DECONSTRUCTION.md, retune.
- Modularity proof fails → fix the seam and re-run the proof; downgrading the
  registry row to "requires code" is allowed only with a written reason and
  costs the "modular" claim for that seam.
- Parity row can't be verified → it's not done. Move it to `v2` explicitly
  (scope decision, logged) or finish it. Silent slippage is the failure mode
  the checklist exists to prevent.
