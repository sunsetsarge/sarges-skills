# Mechanics

Core moveset mechanics and the weapon/weakness system. See `game-feel.md` for the underlying tunables (speeds, timers) referenced throughout this file.

## Dash

Ground dash is the traversal backbone of the genre — it exists to make normal movement feel fast and to be the input that unlocks dash-jump (see `game-feel.md`).

- **Duration**: fixed 0.35 s per activation, regardless of how long the button is held. This is a burst, not a hold-to-sustain speed boost — holding the dash button longer than the activation does nothing extra.
- **Cancelable into jump**: pressing jump at any point during an active dash transitions into a dash-jump, ending the dash state early and carrying its momentum (see `game-feel.md`'s Dash-Jump Momentum Carry rule). This is the primary cancel; it should feel free and immediate, not require a specific timing window.
- **Cooldown**: none required between ground dashes as long as the player is grounded — a grounded player can re-dash again as soon as the current dash's 0.35 s expires and they release/re-press the dash input, subject to whatever input scheme is chosen (tap-to-dash vs double-tap-to-dash; either is genre-valid, tap-with-dedicated-button is simpler to buffer correctly).

### Air dash (optional)

Air dash is a common armor-upgrade unlock (see `progression.md`) rather than a base-kit move, which lets it double as a progression reward.

- Same fixed 0.35 s duration and jump-cancelable rule as ground dash.
- **One air dash per airborne period.** The charge is consumed the instant an air dash activates, and is **not** refilled by landing on a wall-slide or by a wall-jump — it refills only on the tick the player becomes grounded (touches floor). This is a deliberate one-shot-per-hop resource, not a per-second regenerating ability; it exists to extend a jump's horizontal range once, not to enable indefinite hovering.
- Air dash does not reset or add to vertical velocity — it is a horizontal-only burst that temporarily overrides horizontal velocity to dash speed while gravity continues to apply normally beneath it. This keeps it distinct from a "double jump," which resets vertical velocity; air dash should not let the player meaningfully extend total airtime, only horizontal reach.

## Wall-cling and wall-kick

Wall interaction rewards players who \"read\" a vertical shaft rather than punishing them for touching a wall while falling.

- **Activation**: while airborne and falling (vertical velocity > 0 in Y-down convention), if the player holds the directional input into an adjacent solid wall tile, transition to `WallSlide`. There is no separate button — pushing into the wall while falling is the trigger, which keeps the input simple.
- **Wall-slide fall speed**: capped low (75 px/s — see `game-feel.md`), producing a visibly slow controlled descent rather than a full-speed fall. This is what makes clinging a viable navigation tool rather than just a brief animation.
- **Wall-kick (wall-jump)**: pressing jump while wall-sliding launches the character up and away from the wall (vx 200 px/s away, vy -300 px/s — see `game-feel.md`), entering `WallJump` state.
- **Input lock**: for ~0.1 s after a wall-kick, ignore horizontal input opposing the kick direction, so the character visibly clears the wall before the player can steer back into it. Without this lock, players holding "into the wall" (very common, since that's what they were doing to cling) immediately cancel their own wall-jump distance.
- **Chaining up a shaft**: because wall-kick launches the player up and away, and gravity will eventually arc them back toward the opposite wall of a narrow shaft, holding "into wall" again after the input-lock window expires lets the player re-cling to the far wall and repeat — this zig-zag chain is the intended way to climb a vertical shaft with no ladder. Shaft width in level design should be tuned to the wall-jump's horizontal throw (200 px/s over the arc) — see `level-design.md`.

## Variable-height jump

Covered in full in `game-feel.md` (short-hop cut rule). Restated briefly here as a mechanic: a single jump button produces a *range* of jump heights depending on hold duration, via cutting upward velocity by x0.45 on release-while-still-rising. This one rule does the work of a "jump height selector" without extra inputs, and is required for precision platforming sections that mix short hops between close platforms and full-height jumps over tall obstacles.

## Charge buster

The default ranged attack, always available, and its charging is **orthogonal to locomotion** — the player can walk, run, dash, jump, wall-slide, or wall-jump while charging or holding a charged shot. Charge state should never be reset or interrupted by a locomotion state transition; see `architecture.md` for why this must be modeled as a parallel layer rather than folded into the same state machine as movement.

| Tier | Trigger | Typical effect |
|---|---|---|
| Lv1 (uncharged) | Tap fire | Small, fast, low-damage shot. Capped at 3 simultaneous on-screen (see `game-feel.md`). |
| Lv2 | Hold >= 0.55 s | Medium shot: larger hitbox, more damage, often pierces one weak enemy. |
| Lv3 (full charge) | Hold >= 1.1 s | Large signature shot: highest damage, usually pierces multiple enemies, distinct charge-complete visual/audio cue so the player knows it's ready without watching a meter. |

- **Charge persists across state changes**: starting a charge, then jumping, dashing, or wall-sliding, does not reset or pause the charge timer. The charge only resets when the fire button is released (firing the shot at whatever tier was reached) or when the player is hit (see Hit Knockback in `game-feel.md`, which typically interrupts charge as part of the damage-flinch package).
- **Cap enforcement**: the 3-on-screen cap applies to Lv1 shots specifically (they're cheap and spammable); Lv2/Lv3 shots are heavier commitments and are typically exempt or capped much lower (1 in flight), since their long charge time is already a natural rate-limiter.

## Special weapons

Every defeated boss (see `boss-design.md`) grants the player that boss's signature weapon, each with an independent ammo meter separate from the infinite-ammo charge buster.

- **Ammo meter**: a fixed pool (e.g., 28 units on a segmented bar matching player-HP tick size — see `snes-authenticity.md`) that depletes per use and refills from pickups or (rarely) fully on a checkpoint/continue, per project convention — pick one and apply it consistently across all weapons.
- **Mobility-altering weapons**: some special weapons are not just alternate attacks but also modify traversal while equipped or on cast — e.g. a weapon that creates a temporary solid platform in midair, one that grants a brief damage-immune dash through hazards, or one that acts as a grapple/hook for a gap the base moveset cannot cross. These are the primary vector for **hidden-path gating** described in `progression.md` — a stage built with the intro toolkit alone should have visibly-marked spots ("this gap needs the platform weapon") that reward backtracking once that weapon is obtained.
- Weapon selection is typically a menu/quick-select overlay, not itself a locomotion state — treat "currently equipped weapon" as part of the parallel action layer alongside charge/shoot, exactly like the buster.

## Weakness chart — design principle

The weakness chart is a **directed cycle**: each boss/weapon beats exactly one other boss (heavy bonus damage) and loses to exactly one other boss (the boss resists or punishes that weapon), with the cycle wrapping all the way around so there is no single "best" weapon and no dead weapon. This creates:

- **A suggested play order** for a first-time player (start wherever, but beating boss A makes boss B easier, which suggests a route) without a *forced* order — every stage should still be independently clearable with the base buster alone, just harder.
- **A player-facing puzzle**: once 2-3 bosses are down, the player can often infer the rest of the cycle by elimination, which is a satisfying piece of emergent systems-thinking the genre is known for.
- **Weakness-hit feedback**: hitting a boss with its specific weakness should deal significantly more damage (2-3x a normal hit is a common target), and should visibly interrupt — a stagger animation that cancels whatever attack the boss was mid-executing, and at low HP thresholds may skip the boss directly to its next phase or defeat animation. This heavy, legible feedback is what sells "I found the trick" to the player; a weakness that only changes a damage number without any animation tell will go unnoticed by most players.

**Never copy any real game's actual chart or weapon names** — the cycle structure (directed, 8-node, one predator/one prey each) is a genre convention and is fine to reuse; the specific named matchups from any existing game are not.

### Template matrix — original archetypes

Eight original archetypes arranged in a coherent directed 8-cycle. Each beats the next and loses to the previous, wrapping around:

**Flame -> Frost -> Storm -> Volt -> Stone -> Toxin -> Blade -> Gravity -> (back to Flame)**

| Boss (weak against) | Beaten by | One-line justification |
|---|---|---|
| Flame | Gravity | Gravity crushes/smothers open flame, denying it oxygen and airtime. |
| Frost | Flame | Fire melts ice on contact — the most intuitive matchup in the cycle, good as a player's likely first "aha." |
| Storm | Frost | Cold air collapses a storm system's convection, freezing its winds mid-formation. |
| Volt | Storm | A storm's wind and rain disperse/ground a concentrated electrical charge before it can arc. |
| Stone | Volt | Electric current exploits mineral veins in stone, fracturing it from the inside via resonant shock. |
| Toxin | Stone | Stone/mineral compounds neutralize and absorb toxin chemically, acting like an inert filter. |
| Blade | Toxin | Toxin corrodes a blade's edge, dulling and pitting metal that relies on a clean cutting surface. |
| Gravity | Blade | A precise cutting strike severs a gravity field's focal generator/anchor point before it can fully form. |

Reading the table: the left column is the boss being fought; "Beaten by" is the weapon that is *that boss's* weakness. Cross-check: Flame's weapon beats Frost (row 2's "Beaten by"), confirming the cycle direction Flame -> Frost -> Storm -> Volt -> Stone -> Toxin -> Blade -> Gravity -> Flame is consistent both directions through the table.

When building a real project, reskin the archetypes and justifications entirely (different classical elements, different sci-fi/fantasy theme, different justification flavor-text) — reusing this exact 8-cycle structure as a *design pattern* is fine and expected; reusing these exact names in a shipped project is not recommended purely because they're demonstrated here, not because of any IP concern (see `authenticity-and-ip.md` for the actual legal reasoning on why this is safe regardless).
