# Deconstruction Method (Phase 1)

How to reverse-analyze a target app or game into `DECONSTRUCTION.md`. The goal
is a teardown precise enough that someone who never saw the target could
rebuild its *behavior* — while touching none of its protected assets.

## Source hierarchy — use in this order

1. **The target itself.** Play it / drive it, same day you write the doc.
   Screen-record sessions so you can scrub frame-by-frame for feel timing.
2. **Teardowns and postmortems** (GDC talks, dev blogs, wiki mechanics pages,
   speedrun communities — speedrunners document exact frame data and RNG
   rules better than anyone).
3. **Footage** (longplays, reviews) when the target is unplayable/dead.
4. **Docs/help/changelogs** for apps — changelogs reveal which features users
   actually demanded.
5. **Reference source code — LAST, and only after a license check** (Phase 0
   rule). Prefer behavioral observation; source is for confirming constants
   you can't measure, not for copying structure.

## Session protocol

Do at least two deliberate sessions with different hats:

- **Naive user pass:** first-run experience, onboarding, what the target
  teaches and when, where you got confused. This is where the friction list
  comes from.
- **Systems pass:** deliberately probe one system at a time (change one input,
  observe the output). Take timestamped notes; measure, don't estimate —
  count frames, time loads, count clicks-to-task.

## GAME teardown checklist

Work through every row; "n/a" is an acceptable answer, blank is not.

| Area | Capture |
|---|---|
| **Core loop** | The 30-second loop, the 5-minute loop, the session loop. What pulls you around each? |
| **Mechanics inventory** | Every verb the player has (move, shoot, dash, trade...) with exact behavior: input → response, cooldowns, costs, edge cases |
| **Feel & feedback** | Input latency, acceleration/friction curves, easing, hit-stop, screen-shake, particles, audio cues per event, camera behavior. Scrub recordings frame-by-frame; write numbers (e.g. "jump: 4-frame anticipation, apex hang ~120ms") |
| **Systems** | Progression (XP/unlocks), economy (sources/sinks/prices), difficulty curve (what scales, when), state (save model, run structure, permadeath?) |
| **Content structure** | Levels/waves/screens: how many, how ordered, what varies per unit of content, what's data vs. bespoke |
| **Enemy/AI design** | Behavior archetypes, spawn logic, telegraphs, boss phase structures |
| **UX/UI** | HUD elements + when they appear, menu tree, pause behavior, settings offered |
| **Audio/visual style** | Palette discipline, readability rules (how does it keep the action parseable?), music structure per state. Style is cloneable as *approach*, not as *assets* |
| **Tech guess** | Platform, resolution/tick rate, likely architecture, what's obviously data-driven in the original (moddable files are a gift — they reveal the data schema) |

## APP teardown checklist

| Area | Capture |
|---|---|
| **Core value loop** | The job-to-be-done: what does the user come in with, leave with, and how often? |
| **Feature inventory** | Every screen and every action on it; the primary path and every secondary path |
| **Information architecture** | Nav structure, entity model (what are the nouns and their relationships), search/filter/sort capabilities |
| **Workflows** | Clicks/keystrokes for the top 5 tasks — measured. These are the parity *and* improvement baselines |
| **Feel & feedback** | Perceived responsiveness (time-to-interactive, action-to-confirmation), micro-interactions, loading/skeleton states, **empty states, error states, undo** — the trio most clones forget |
| **State & data** | What persists, where; offline behavior; import/export; multi-device story |
| **Systems** | Permissions/accounts, notifications, integrations, settings surface |
| **Onboarding** | First-run flow, defaults, what it teaches vs. assumes |
| **Tech guess** | Platform, storage shape, sync model, what's config vs. code |

## The two named outputs (mandatory)

End `DECONSTRUCTION.md` with these two sections — they drive Phases 2–4:

1. **Fun/value core (~20%).** The small set of mechanics/features that carry
   the target. Test: "if only this shipped, would it still be recognizably
   worth using?" Everything in this list is protected through every scope
   cut and gets the vertical slice.
2. **Friction & dated seams.** Concrete, observed problems (with your
   measurements) — load times, click counts, missing undo, unreadable UI,
   difficulty spikes, dated control schemes. This list becomes the
   improvement thesis in `CLONE_PLAN.md`. If it's empty, you did the naive
   user pass wrong.

## Anti-patterns

- **Cloning from memory.** You will invent features the target never had and
  miss ones it did. Verify every checklist row against the live target or a
  recording.
- **Transcribing instead of measuring.** "Jumps feel floaty" is not
  reproducible; "0.35s to apex, 0.5s down, air control ~60%" is.
- **Cataloguing content instead of structure.** You need the *shape* of level
  3 (what it introduces, how it escalates), not its layout — the layout is
  the original's expression; the escalation pattern is the mechanic.
