# Boss Design

## Table of contents

- [Multi-phase fights](#multi-phase-fights)
- [Attack patterns as data](#attack-patterns-as-data)
- [Telegraphing](#telegraphing)
- [Weakness reaction](#weakness-reaction)
- [The ritual intro sequence](#the-ritual-intro-sequence)
- [Boss health bar conventions](#boss-health-bar-conventions)
- [Arena design](#arena-design)
- [Difficulty knobs](#difficulty-knobs)
- [Boss-design worksheet template](#boss-design-worksheet-template)

## Multi-phase fights

Target **2-3 phases per boss**, triggered by HP thresholds rather than a timer — thresholds keep the fight's pacing tied to player performance (a player doing heavy weakness damage reaches phase 2 faster, which feels earned) rather than dragging on a fixed clock regardless of how well the player is doing.

- Common thresholds: phase 2 at 66% HP, phase 3 (if used) at 33% HP. A 2-phase boss simply uses the 50% threshold instead.
- Each phase should add or swap attack patterns — never merely "the same patterns but faster," which reads as artificial difficulty rather than a real escalation. At minimum, phase 2 should introduce one attack not seen in phase 1.
- A weakness hit that crosses a phase threshold should trigger the phase transition immediately (interrupting whatever attack was mid-execution) rather than waiting for the current attack to finish — this is part of why weakness hits feel powerful (see Weakness reaction below).

## Attack patterns as data

Model each boss's moveset as a data table, not hardcoded control-flow, so encounter design is tunable without touching code and so the "attack table" is directly reviewable during design.

| Field | Purpose |
|---|---|
| Attack ID | Unique name/key for the attack. |
| Weight | Relative selection probability when the boss's AI picks its next attack (e.g., a heavy signature attack might have lower weight than a common jab). |
| Cooldown | Minimum time (seconds) before this specific attack can be selected again, preventing back-to-back repeats of the same pattern. |
| Positional precondition | Required spatial relationship to the player for this attack to be eligible (e.g., "player within melee range," "player airborne," "player at range >150px"), so the AI doesn't fire a melee swing at a player across the room. |
| Phase availability | Which phase(s) this attack is allowed in — an attack can be phase-1-only, phase-2-onward, etc. |
| Telegraph duration | Wind-up frames before the attack becomes active/dangerous (see Telegraphing below). |
| Active hitbox duration | How long the attack's hitbox is actually dangerous, once telegraph ends. |
| Recovery duration | Post-attack vulnerable window before the boss can act again — this is usually the best (sometimes only) damage-dealing window for the player, so it should be long enough to matter (a few of the player's own attack cycles) but not so long the boss feels helpless. |

AI selection loop per decision point: filter the table to attacks whose phase and positional precondition currently match and whose cooldown has expired, then weighted-random-pick among the remaining eligible set. This keeps boss behavior legible (a human designer can read the table and predict likely patterns) while still feeling non-scripted run to run.

## Telegraphing

Every attack must be readable before it becomes dangerous — this is the single most important fairness rule in boss design for this genre, since bosses hit hard and often occupy most of the screen.

- **Wind-up animations >= 20 frames (at 60 Hz, ~0.33 s) for heavy attacks.** Lighter, cheaper attacks can telegraph shorter, but nothing should go from "idle" to "active hitbox" with zero visible wind-up — that reads as a cheap hit, not a dodged-or-not-dodged skill check.
- **Distinct silhouette per attack.** The boss's pose during wind-up should be visually distinguishable attack-to-attack (raised arm vs crouch vs glow-charge stance) so an experienced player can identify which attack is coming from the silhouette alone, before needing to read a tell like a projectile spawning.
- **Distinct audio cue per attack**, layered on top of the visual tell — a charge-up sound, a roar, a distinct trigger SFX. Audio telegraphs matter especially for attacks that originate off-screen or during screen-shake/flash moments when the visual read is briefly degraded.

## Weakness reaction

When hit with a boss's specific weakness weapon (see `mechanics.md`'s weakness chart), the reaction should be dramatically more legible than a normal hit:

- **Heavy bonus damage** (2-3x a normal hit, tune per project).
- **Stagger animation**: a distinct flinch/stagger pose plays, different from the normal small hit-react, long enough to read clearly (a fixed handful of frames, e.g. ~15-20).
- **Attack interrupt**: if the boss was mid-telegraph or mid-active-hitbox on an attack when the weakness hit lands, cancel that attack outright rather than letting it complete — this is what makes weakness hits feel like they matter tactically, not just numerically.
- **Possible phase-skip**: if a weakness hit's damage crosses a phase threshold, the phase transition fires immediately (see Multi-phase fights above); at very low remaining HP a sufficiently large weakness hit can plausibly skip straight to the defeat sequence, which is a fine and intentional "I found the trick and it's paying off huge" moment.

## The ritual intro sequence

A fixed beat-by-beat sequence establishes stakes and hands control back to the player only once the stage is fully set — consistency across all bosses matters here since players learn to expect and skip through this ritual by its second occurrence.

1. **Door/shutter seal**: on entering the boss arena trigger zone, a door or shutter closes behind the player, visually confirming the arena is now locked (see `level-design.md`'s camera-lock note) — this happens before the boss appears, establishing "you're committed" first.
2. **Boss walk-in / entrance pose**: the boss enters from off-screen or drops/rises into the arena with a distinct entrance animation and a held intro pose — the player is not yet in control during this beat.
3. **Name splash**: the boss's name (and optionally title/epithet) displays on screen, typically alongside its portrait.
4. **Health bar fill, tick-by-tick**: the boss's health bar animates filling up from empty to full over a short duration (not an instant pop to full), giving weight to the amount of HP the player is about to have to whittle down.
5. **Control returns to the player** only after the health bar finishes filling — never before. Handing control back mid-animation risks a cheap early hit or, worse, a player input getting eaten by the still-playing cutscene.

Keep the whole sequence brisk (a few seconds total) — its value is ritual weight on *first* viewing per boss; if it overstays on repeat attempts (common, since players re-fight bosses after dying) it becomes a skippable annoyance, so make sure it is either short enough to tolerate every retry or explicitly skippable on retry.

## Boss health bar conventions

- **Segmented**, using the **same tick size as the player's own HP bar** (see `snes-authenticity.md` and `progression.md`'s heart-tank math) — this shared visual unit lets the player directly compare "how much of the boss is left" against "how much of me is left" at a glance, which is a core piece of the genre's tension-reading UI.
- Position it prominently but without obscuring the arena — typically top of screen, opposite the player's own HP bar.
- Depleting the bar to zero triggers the boss's defeat sequence (explosion/dissolve animation, weapon-grant pickup drop, transition out of the arena-lock state) — see `mechanics.md` for what the player receives.

## Arena design

- **Flat, with 1-2 features** — a boss arena is not a platforming challenge in itself; it should be mostly open flat ground so the fight's difficulty comes from the boss's attacks and the player's positioning/dodging, not from fighting the geometry. The 1-2 features (a raised platform, a pit, a single pillar) exist to give the fight *some* verticality/cover options without turning it into a full obstacle course.
- **Wall-jumpable walls**: if the arena has side walls the player can be pushed/knocked into, make them wall-jumpable (matching the standard wall-kick rules in `game-feel.md`/`mechanics.md`) so a boss's knockback attack doesn't strand the player against a dead wall with no recovery option.
- Arena width/height should comfortably fit the range of the boss's longest-reaching attack plus dodge room on both sides — test this explicitly per boss rather than reusing one arena template for every fight.

## Difficulty knobs

Tune these independently per boss rather than scaling everything uniformly, so each fight can have its own identity (a fast-aggressive boss vs a slow-heavy-hitting boss feel different even at similar overall difficulty):

- **HP total** (fight length/attrition).
- **Attack weight distribution** (how often the dangerous/hard-to-read attacks are selected vs safer filler attacks).
- **Cooldown lengths** (how much recovery/breathing room the player gets between attacks).
- **Telegraph duration** (can be tightened for a harder/faster-reacting boss, but never below the ~20-frame heavy-attack floor above without a strong, distinct compensating tell).
- **Damage per hit and knockback strength** (see `game-feel.md`'s hit-knockback values as the baseline; a harder boss can hit for more HP without needing a longer stagger-lock, which would compound punishingly).
- **Phase count and threshold placement** (a 3-phase boss with tight thresholds reads as more relentless than a 2-phase boss even at equal total HP).

## Boss-design worksheet template

Use this Input -> Output structure when designing a new boss: start from theme and weakness assignment (from the weakness-chart cycle in `mechanics.md`), then fill the attack table.

**Input**: Theme = Frost. Weakness = Flame (per the template cycle in `mechanics.md`). Beats = Storm.

**Output** — filled attack table for an original "Frost" archetype boss:

| Attack ID | Weight | Cooldown | Positional precondition | Phase | Telegraph | Active hitbox | Recovery |
|---|---|---|---|---|---|---|---|
| Ice Shard Volley | 4 | 2.5 s | Player at range > 100px | 1-3 | 25 frames (crouch + glow) | 12 frames (3 shards fired in sequence) | 30 frames |
| Frost Slide Charge | 3 | 3.0 s | Player at range 50-200px, same floor level | 1-3 | 20 frames (crouch, ice crackling sound) | 18 frames (sliding hitbox travels full arena width) | 45 frames (recovers slowly from overextension) |
| Ice Pillar Slam | 2 | 4.0 s | Player within melee range (<60px) | 1-3 | 22 frames (raised arm, distinct roar) | 8 frames (slam impact + brief AOE at landing point) | 35 frames |
| Blizzard Field (room-wide hazard) | 2 | — (once per phase, not on normal cooldown) | Any | 2-3 only | 40 frames (boss plants and glows brightest blue, loud wind-up SFX) | Persists 3 s (arena-wide slow zone + periodic damage ticks) | 20 frames after field ends |
| Weakness reaction: Flame hit | n/a | n/a | n/a | Any | n/a | Stagger 18 frames, cancels current attack, 2.5x damage | n/a |

Notes on this worked example: phase 2 introduces Blizzard Field as the escalation beat (per the Multi-phase-fights rule that phase 2 must add something new); Frost Slide Charge's long recovery (45 frames) is intentionally the fight's best punish window, telegraphed by its own long wind-up so a player who dodges it correctly is rewarded with a clear counter-attack opportunity; the Flame weakness reaction row is not a boss-initiated attack but documents the required response behavior alongside the attack table for design-review completeness.
