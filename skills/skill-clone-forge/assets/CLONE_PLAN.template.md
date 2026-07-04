# CLONE_PLAN — <Clone Name> (← <Target>)

> Canonical copy: this file at the repo root. Survivor copy: Confluence, under
> Project Logs hub (ancestor 98494) — update both at each phase gate; repo
> wins if they disagree.

**Repo:** `C:\Claude\Projects\Active\<Project>\`
**Status:** Phase <n> — <one line>
**Last updated:** <date>

## Clone charter (from Phase 0)

<One paragraph: what we clone (mechanics/systems/UX layer), what we replace
with originals (name, art, audio, story, branding), and the improvement
thesis — the reason this clone deserves to exist.>

**Protected layer we will NOT reproduce:** <target name/trademarks, logos,
art, music, characters, dialogue, distinctive assets>
**Reference source used:** <none | repo + license + what we took from it>

## Objective

<2–3 sentences: what ships at v1, for whom, on what platform.>

## Feature-parity checklist

Tiers: `v1-slice` | `v1` | `v2` | `cut` (cuts need a reason). Every non-cut
v1 row must be ticked with a how-verified note before the Phase 5 gate.

| # | Target feature | Tier | Build task | Verified how | ✓ |
|---|---|---|---|---|---|
| 1 | <feature from DECONSTRUCTION.md> | v1-slice | <task> | | ☐ |
| 2 | | v1 | | | ☐ |
| 3 | | v2 | | | ☐ |
| 4 | <feature> | cut | — (<reason>) | — | — |

## Improvement thesis (additions — kept separate from parity)

| # | Improvement | Measure (before → target) | Tier | ✓ |
|---|---|---|---|---|
| A | <e.g. undo everywhere> | <target: 0 undoable actions → 100%> | v1 | ☐ |
| B | <e.g. load time> | <target: 8s → <2s> | v1 | ☐ |

## Quality bar (numbers set now, scored at Phase 5)

Variant: **GAME / APP** (see quality-and-parity.md for the full rubric)

| Line | Budget for this clone |
|---|---|
| Perf (fps / time-to-interactive) | <e.g. 60fps mid-hardware / <2s TTI> |
| Load/boot | <e.g. <3s> |
| Feedback density | <e.g. no silent core-loop events> |
| Accessibility floor | <rubric floor + any extras> |
| Feel fidelity anchors | <the 3–5 measured numbers from DECONSTRUCTION.md to match> |

## Phased scope

| Phase | Contents | Runs on | Gate |
|---|---|---|---|
| 0 IP & charter | charter above | Fable/Opus | charter written |
| 1 Deconstruct | DECONSTRUCTION.md | Fable/Opus | fun core named |
| 2 Spec | this file | Fable/Opus | checklist tiered, bar numeric |
| 3 Architecture | ARCHITECTURE.md | Fable/Opus | ≥3 seams registered |
| 4a Vertical slice | <v1-slice rows> | Sonnet build / Opus review | slice is fun/useful, smoke-tested |
| 4b Parity build | <v1 rows, module order> | Sonnet build / Opus review | per-module smoke tests, milestone commits |
| 5 Gate | validation report | Fable/Opus judge (≠ builder) | all four gates pass |

## Tech stack

<From the stack-picker in modular-architecture.md, with one line of why.>

## Risks

| Risk | Mitigation |
|---|---|
| <e.g. feel fidelity of X is hard to measure> | <frame-scrub recordings; tune against numbers> |
| <e.g. scope creep past parity> | <v2 tier exists; additions live in the thesis table only> |

## Log

- <date> — Phase 0–2 complete; survivor copy published (page <id>)
- <date> — <milestone>
