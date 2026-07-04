# Game Feel — Physics and Tunables

Genre-defining feel comes from a specific combination of instant acceleration, floaty-but-controlled jump arcs, and a small set of forgiveness windows (coyote time, jump buffering) that make the player feel more precise than they actually were. None of the individual numbers below matter as much as their *ratios* to each other — dash should feel roughly 2-2.5x walk speed, jump should clear a 4-tile gap when dash-jumping, etc. Tune by feel against a real level, not in isolation.

All values below are **felt/tuned starting points**, not physical simulation targets. This genre is not simulating real gravity — it is simulating "1990s 2D action game" muscle memory. Treat every number as a dial to re-tune once a level block-out exists.

## Core tunables

| Parameter | Start value | Notes |
|---|---|---|
| Internal resolution | 256 x 224 | Authentic SNES framebuffer. Render at this resolution and integer-scale up (2x, 3x, 4x) for the display — never stretch with non-integer scaling, which introduces uneven pixel sizes and shimmer on scrolling. |
| Fixed tick | 60 Hz | Run all gameplay logic (physics, collision, state machines, input reads) in a fixed-timestep step, decoupled from render framerate. This is what makes frame-perfect tricks (and fair hitboxes) possible and reproducible. |
| Gravity | 900 px/s² | Tune range 800-1000. Lower feels floaty/moon-like; higher feels heavy and reduces air control usefulness. |
| Walk speed | 90 px/s | Baseline traversal speed, no ramp. |
| Dash speed | 210 px/s | ~2.3x walk. Duration 0.35 s per activation (see Mechanics doc for cancel rules). |
| Jump velocity | -330 px/s | Up is negative in a Y-down coordinate convention. Initial impulse applied instantaneously on jump-press, not ramped. |
| Short-hop cut | x0.45 on release while rising | If jump is released while vertical velocity is still negative (still ascending), multiply remaining upward velocity by 0.45. This is what produces variable jump height from a single jump button — tap for a short hop, hold for full arc. |
| Terminal fall speed | 450 px/s | Cap downward velocity here. Without a cap, long falls become unreadable (player can't judge landing timing) and can clip through thin one-way platforms at high tick-rate edge cases. |
| Wall-slide fall speed | 75 px/s | Separate, much lower cap applied only while wall-sliding (see Mechanics doc). This is what makes wall-cling read as a deliberate slow descent rather than "still falling." |
| Wall-jump impulse | vx 200 px/s away from wall, vy -300 px/s | Roughly matched to a normal jump's height but with strong forced horizontal push so the player visibly leaves the wall rather than re-sticking to it. |
| Wall-jump input lock | ~0.1 s | Horizontal input is ignored for this window after a wall-jump so the outward kick reads on screen before the player can fight it with the stick/pad. Too long feels unresponsive; too short and the wall-jump looks like it didn't happen. |
| Dash-jump carry | 210 px/s horizontal carried into jump velocity | The signature long-jump move of the genre — see dedicated section below. |
| Coyote time | 0.08 s | Window after walking off a ledge during which a jump input still succeeds, as if the player were still grounded. See dedicated section below. |
| Jump buffer | 0.10 s | Window before landing during which a jump press is queued and fires the instant the player becomes grounded. See dedicated section below. |
| Hit knockback | vx 60 px/s away from damage source | Paired with 1.0 s invincibility frames (sprite blinks during this window) and 0.25 s of control lock during the knockback itself. |
| Charge tiers | Tap = Lv1 (uncharged); hold >= 0.55 s = Lv2; hold >= 1.1 s = Lv3 | Max 3 uncharged (Lv1) shots allowed on screen simultaneously — firing a 4th despawns the oldest or is simply blocked, tune per feel. Charged shots are typically exempt from this cap since only one is usually in flight. |

## Acceleration, deceleration, and turnaround

Genre convention is **near-instant** ground acceleration and deceleration — this is not a racing game. On ground:

- **Acceleration to max walk speed**: 1-3 ticks (at 60 Hz, ~16-50 ms). Effectively snaps to max speed; do not use a slow ramp-up curve.
- **Deceleration to zero on input release**: also 1-3 ticks. The character should stop almost instantly when the stick is released, not slide.
- **Turnaround** (input reversed while moving): allow a brief skid — 2-4 ticks — with a distinct turnaround animation frame. This is the one place a *tiny* bit of momentum persistence is genre-authentic; it sells weight without costing control. Do not apply this same skid to the accel/decel-to-zero cases above.

Rationale: platforming precision in this genre depends on the player's mental model being "I am standing exactly where I stopped pressing." Any noticeable coast-to-stop breaks precise ledge platforming and reads as "slippery" — reserve slipperiness deliberately for ice-gimmick stages (see `level-design.md`), where it becomes a stage hazard rather than default player physics.

## Landing recovery

**None.** There is no landing lag, no forced animation lock, no recovery frames after touching ground from a fall or jump — the player regains full run/jump/dash control on the exact tick the grounded check succeeds. This is a deliberate genre contract: the player is never punished for choosing to fall rather than platform carefully, which keeps momentum-driven traversal (dash-jump chains, corner-cuts) viable throughout a level rather than only near the ground.

## Input-reading order per tick

Read and resolve input in a fixed order every fixed tick so behavior is deterministic and frame-perfect tricks are reproducible:

1. **Buffer intake** — record any new button-down events (jump, dash, shoot, weapon-switch) into their respective buffer windows, decrementing existing buffer timers.
2. **State transition check** — evaluate the locomotion FSM (see `architecture.md`) against current physical state (grounded/airborne/walled) plus buffered inputs. Consume a buffered input if it triggers a transition (e.g., buffered jump firing on landing).
3. **Horizontal velocity resolution** — apply acceleration/deceleration/turnaround rules based on held directional input and the current locomotion state.
4. **Vertical velocity resolution** — apply gravity, terminal velocity caps, short-hop cut (checked against jump-release this tick), wall-slide cap.
5. **Position integration** — apply resolved velocity to position.
6. **Collision resolution** — resolve against tilemap, X axis then Y axis (see `architecture.md` for why X-then-Y ordering matters for corner cases).
7. **Post-collision state correction** — update grounded/walled/ceiling flags from the collision result; this feeds next tick's state transition check.
8. **Orthogonal action layer** — resolve charge/shoot/weapon state independently of the above (see `architecture.md`'s parallel action layer). This must never gate or be gated by locomotion transitions.

Keeping this order fixed and separate from rendering is what makes coyote time, jump buffering, and dash-off-ledge behavior (below) consistent frame to frame instead of flickering based on render timing.

## Dash-jump momentum carry (first-class rule)

Dash-jump is the genre's signature long-jump technique: dash along the ground, then press jump before the dash timer expires, and the character leaps while keeping dash-speed horizontal momentum instead of decelerating to walk speed first.

Exact rule:

- If jump is pressed while the dash state is active (ground dash, timer not yet expired) **or** within the coyote window immediately after a ground dash carries the player off a ledge (see below), set horizontal velocity to dash speed (210 px/s, signed by facing/dash direction) and vertical velocity to jump velocity (-330 px/s) in the same tick.
- The resulting airborne state is `DashJump`, not plain `Jump` — this matters for animation and for whether a second air-dash is still available (see `mechanics.md`; landing/dash-jumping does not by itself refresh the air-dash charge, only touching ground does).
- Horizontal velocity during a dash-jump is **not** re-decelerated to walk speed — it persists at dash speed for the rest of that airborne arc, and only decays via normal air-drift rules if the player actively pushes the opposite direction.
- This is what lets a dash-jump clear roughly 2x the horizontal distance of a standing jump — the number to check when block-out testing a gap is "does dash-jump clear it, does standing jump fail it," which is the intended skill gate.

## Coyote time (semantics)

Coyote time exists to absorb the gap between "player perceives themselves as still grounded" and "physics says they left the ground," which on a 60Hz tick with human reaction time is a real and unfair-feeling gap if not compensated.

Exact rule:

- Start an 0.08 s coyote timer the instant the grounded state transitions to false **for a reason other than jumping** (i.e., walking or dashing off a ledge — not for a jump the player just performed, which should not re-trigger coyote).
- While the coyote timer is active and the player has not already jumped since leaving ground, a jump press is treated exactly as if the player were still grounded: it succeeds, consumes the timer, and — critically — **inherits whatever horizontal state was active at the moment of leaving the ground**. If the player was mid-dash when they walked/dashed off the edge, a coyote-window jump is a dash-jump (see above), not a plain jump.
- The coyote timer is cancelled immediately if the player jumps, or if it simply expires.

## Jump buffering (semantics)

Jump buffering exists for the symmetric case: player presses jump slightly *before* landing, intending to chain a jump the instant they touch down, rather than needing to time the press to a specific landing frame.

Exact rule:

- Any jump press while airborne and not otherwise consumed (i.e., not already used for a wall-jump or a coyote-jump) starts a 0.10 s buffer timer holding "jump requested."
- Every tick while airborne, check: if grounded-this-tick is true AND the buffer timer is still active, fire a jump immediately using this tick's landing as the "grounded" moment, and clear the buffer.
- The buffered jump does **not** inherit dash state the way a coyote-jump does — it's a fresh grounded jump, because the player's dash (if any) will have already ended or been overwritten by whatever they were doing in the air. If the player is dashing again on landing (e.g., re-pressed dash while still airborne) normal dash-jump rules apply independently.

## Dash-off-a-ledge edge case (first-class rule)

This is the interaction that most implementations get wrong, so state it explicitly as one connected rule:

1. Player ground-dashes and runs off a ledge mid-dash. Horizontal velocity stays at dash speed (210 px/s) — dashing does not have its own "falls off ledge" special case, it simply becomes airborne while retaining current velocity, same as walking off a ledge retains walk speed.
2. Gravity begins applying immediately on becoming airborne (no grace period on gravity onset itself — the grace period is entirely about the jump *input*, via coyote time, not about suspending physics).
3. The coyote timer (0.08 s) starts now, per the rule above.
4. **If the player presses jump within the coyote window**: this becomes a dash-jump per the Dash-Jump Momentum Carry rule — horizontal velocity is (re-)set to dash speed and vertical velocity to jump velocity, and the airborne state is `DashJump`. This is intentional and is the primary way players discover/execute dash-jumps off ledges rather than only from a flat run-up.
5. **If the player does not jump and the dash timer (0.35 s from dash activation) expires while still airborne with no jump input**: horizontal velocity decays from dash speed down to walk speed (90 px/s) over a short interval (2-4 ticks, matching the turnaround feel) rather than instantly clamping. This is the chosen rule — dash speed is a temporary state tied to the dash timer, not a permanent velocity floor, so a dash that runs out mid-air settles back to normal air-drift speed rather than launching the player unrealistically far on every dashed-off ledge. Instant clamp is a valid alternative but reads as an abrupt speed change; prefer the short decay.
6. If the player pushes the opposite direction during the decay or after it, normal air deceleration/turnaround applies on top of whatever speed remains.

Document this rule exactly as written when implementing — it is the single most-tested interaction in a genre run (speedrunners and casual players alike probe ledge-dash-jump timing within the first few minutes of play), and an inconsistent rule here reads as "broken physics" faster than almost anything else in the moveset.
