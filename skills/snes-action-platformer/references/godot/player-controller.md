# Player Controller (Godot 4.3+)

Explains how `templates/player_controller.gd` is structured and why. Read this before modifying the template — the FSM shape, timer semantics, and mover choice below are load-bearing decisions, not arbitrary style.

## Table of Contents

- [FSM Pattern](#fsm-pattern)
- [States](#states)
- [Parallel Action Layer (Charge/Shoot)](#parallel-action-layer-chargeshoot)
- [Coyote Timer and Jump Buffer](#coyote-timer-and-jump-buffer)
- [Dash-Jump Momentum Carry](#dash-jump-momentum-carry)
- [Hurt / I-Frame Flow](#hurt--i-frame-flow)
- [Mover Choice](#mover-choice)

## FSM Pattern

The template uses an `enum State { ... }` plus a `match current_state:` dispatcher called once per physics tick, with three hooks per state: `_enter_state(state, prev_state)`, inline per-tick logic in the match arm, and `_exit_state(state, next_state)`. This is simpler than a full class-per-state pattern (no separate State objects/inheritance) and is fast enough for a single player character with ~10 states — a class-per-state pattern earns its complexity when you have dozens of states or need states shared across multiple actor types, neither of which applies here.

Concretely: `_physics_process(delta)` calls `_update_timers(delta)` first (coyote, buffer, i-frame, wall-jump-lock, dash-duration — all just counting down), then reads input, then runs `match current_state` where each arm computes velocity for this tick and may call `_change_state(new_state)`. `_change_state` calls `_exit_state` on the old state, reassigns `current_state`, then calls `_enter_state` on the new one, so setup/teardown logic (like starting the dash timer on entering Dash, or zeroing horizontal input lock on exiting WallJump) lives in exactly one place instead of being scattered across every arm that might transition into or out of that state.

## States

`Idle`, `Run`, `Jump`, `Fall`, `Dash`, `DashJump`, `WallSlide`, `WallJump`, `Hurt`, `Dead`.

- **Idle**: grounded, no horizontal input. Watches for move input (-> Run), jump input (-> Jump), dash input (-> Dash).
- **Run**: grounded, horizontal input held. Applies `walk_speed` in input direction. Watches for input release (-> Idle), jump (-> Jump), dash (-> Dash), losing floor contact without jumping (-> Fall, this is what coyote time covers).
- **Jump**: airborne, moving upward (vy < 0 immediately after a jump). Applies gravity every tick. Watches for jump-button release while still rising (apply the ×0.45 cut, see below) and for vy crossing 0 (-> Fall).
- **Fall**: airborne, vy >= 0. Applies gravity clamped at `terminal_fall_speed`. Watches for landing (`is_on_floor()` -> Idle or Run depending on held input), wall contact while airborne (-> WallSlide), dash input if dash available (-> Dash, i.e. air-dash is allowed by default in the template — comment clearly if a project wants to disable air dash).
- **Dash**: ground or air, fixed `dash_speed` for `dash_duration` (0.35s), gravity typically suppressed or reduced during a ground dash (template suppresses gravity only while `is_on_floor()` is true during the dash, so an air-dash still falls slightly, matching MMX's dash-jump feel). Watches for the dash timer expiring (-> Run/Idle/Fall depending on ground contact), and for jump input during the dash (-> DashJump, carrying momentum, see below).
- **DashJump**: a Jump variant that starts with `velocity.x` preset to the dash's horizontal speed/direction instead of snapping to `walk_speed`. Same gravity/jump-cut rules as Jump. Watches for the same landing/apex transitions as Jump/Fall.
- **WallSlide**: airborne, touching a wall (`is_on_wall()` true via facing raycast, see Mover Choice), pressing input into the wall, vy > 0 (falling). Clamps fall speed to `wall_slide_speed` (75 px/s) instead of `terminal_fall_speed`. Watches for jump input (-> WallJump), for input released away from the wall (-> Fall), for landing (-> Idle).
- **WallJump**: fires `wall_jump_vx`/`wall_jump_vy` away from the wall the instant it's entered, and starts the `wall_jump_lock_duration` (0.1s) timer during which horizontal input is deliberately ignored — see rationale below. Otherwise behaves like Jump (gravity, jump-cut on early release, watches for apex -> Fall).
- **Hurt**: entered on taking damage. Applies knockback velocity, starts the 0.25s control-lock timer (input ignored for both axes), and separately starts the 1.0s i-frame timer (see Hurt/I-Frame Flow — these two timers are different lengths and independent). Watches for the control-lock timer expiring (-> Idle if grounded, Fall if not) — note i-frames may still be counting down after control returns, which is correct MMX-style behavior, not a bug.
- **Dead**: entered when HP <= 0 (checked wherever damage is applied, typically by whatever calls into the controller from the Hurtbox's `hit_taken` signal). Freezes physics-driven movement, plays death sequence/animation, and is a terminal state until an external respawn/reset call (from GameState/SaveManager checkpoint logic) resets the controller.

Why the wall-jump input lock exists: without it, a player holding the direction *into* the wall (which is how they got into WallSlide in the first place) would have their own held input immediately fight the wall-jump's outward velocity the very next tick, effectively canceling the wall-jump into a near-vertical hop that never clears the wall. Locking horizontal input for 0.1s forces the outward velocity to actually carry the character away from the wall before input can influence velocity.x again — long enough to clear the wall, short enough that it doesn't feel like lost control.

## Parallel Action Layer (Charge/Shoot)

Shooting and charging are **not** locomotion states. A player can run-and-gun, jump-and-shoot, dash-and-shoot, wall-slide-and-shoot — baking "Shoot" into the locomotion enum would require a cross-product state for every combination (`RunShoot`, `JumpShoot`, `DashShoot`...), which is exactly the kind of state explosion FSMs are supposed to avoid.

Instead, the template ticks a small, independent set of variables every `_physics_process`, alongside (not inside) the locomotion `match`:

```gdscript
var is_charging: bool = false
var charge_time: float = 0.0
var shots_fired_this_frame: int = 0  # reset each tick, informational
```

Each physics tick, regardless of `current_state`: if the shoot action is held, increment `charge_time` and set `is_charging = true`; if shoot is released, read `charge_time` against `charge_tier_2_time` (0.55s) and `charge_tier_3_time` (1.1s) to decide which tier of shot to fire, then reset `charge_time = 0.0` and `is_charging = false`. This runs identically whether `current_state` is `Idle`, `Jump`, `Dash`, or anything else — locomotion and the action layer read the same input map but never branch on each other's state (with one deliberate exception: `Hurt` and `Dead` states short-circuit the action layer entirely, since you can't shoot while flinching or dead — check `current_state` at the top of the action-layer tick and early-return for those two).

## Coyote Timer and Jump Buffer

Both stored as plain countdown floats, decremented in `_update_timers(delta)`, never allowed below 0.

- **`coyote_timer: float`**: reset to `coyote_time` (0.08s) the instant `is_on_floor()` is true. Decremented every tick thereafter. The jump-input check treats "can jump" as `is_on_floor() or coyote_timer > 0.0` — so a jump pressed up to 0.08s after walking off a ledge still fires, because the timer hasn't hit zero yet even though the floor check just went false.
- **`jump_buffer_timer: float`**: reset to `jump_buffer_time` (0.10s) the instant the jump action is pressed (`Input.is_action_just_pressed("jump")`), regardless of whether the player is currently allowed to jump. Decremented every tick. On any tick where `is_on_floor()` becomes true (landing), check `jump_buffer_timer > 0.0` — if so, immediately fire a jump and zero the buffer, rather than requiring the player to press jump again after landing.

Both timers are checked, not just set-and-forget: the actual jump-fire logic is `if (is_on_floor() or coyote_timer > 0.0) and (Input.is_action_just_pressed("jump") or jump_buffer_timer > 0.0):` — read that as "the player is grounded-enough AND has expressed jump intent recently enough," which is what makes both grace periods stack correctly (e.g. you can buffer a jump while still in coyote time from a *previous* ledge, though in practice these windows are short enough this rarely matters).

## Dash-Jump Momentum Carry

Pressing jump during (or within a tick or two of) a dash should not snap horizontal velocity back down to `walk_speed` — that reset feels like the dash "didn't count" and kills the fast-traversal feel that makes dashing worth using. The template's approach: on transitioning Dash -> DashJump, copy the dash's current `velocity.x` directly into the new state instead of recomputing it from `walk_speed` and input direction. From there, DashJump does **not** actively decay `velocity.x` — it lets normal air-control input override it if the player pushes the opposite direction, but applies no forced deceleration of its own. This is the "looser air control lets vx persist" approach rather than an explicit decay-over-time curve: simpler to implement and tune (one clamp value: air acceleration/deceleration rate, applied uniformly, rather than a separate decay curve just for this transition), and it still reads correctly because a player who does nothing with the stick keeps the full dash speed all the way through the jump arc, while a player who actively steers gets normal responsive air control. If a project wants a harder MMX-authentic feel (dash speed bleeding off toward walk_speed over the jump's air time even with no input), swap in an explicit `lerp` toward `walk_speed` gated on time-since-dash-jump-started — the template comments this alternative inline at the DashJump state block.

## Hurt / I-Frame Flow

Sequence, matching MMX-style damage feedback:

1. Something (a Hurtbox's `hit_taken` signal, see `combat.md`) calls into the player controller's damage entry point with `amount`, `source_position`, `weapon_id`.
2. Controller checks its own i-frame flag first — if already invulnerable, the call is a no-op (this check typically also lives on the Hurtbox itself via `monitoring = false`, so in practice the controller rarely even receives a second call mid-i-frames, but the controller-side check is a cheap belt-and-suspenders guard).
3. If not invulnerable: apply damage to HP (via GameState), compute knockback direction (away from `source_position`, magnitude `knockback_vx` = 60 px/s on the horizontal axis — vertical knockback is typically left at 0 or a small upward pop, template uses 0 vertical to keep it predictable), transition to `Hurt` state.
4. `Hurt` state entry starts **two independent timers**: `control_lock_timer = knockback_lock_duration` (0.25s, during which all player input is ignored so knockback actually displaces the character) and separately `iframe_timer = iframe_duration` (1.0s, during which the Hurtbox's `monitoring` is set false and/or a flag blocks further `take_damage` calls).
5. Sprite flicker during i-frames: toggle `modulate.a` between `1.0` and e.g. `0.4` on a fixed interval (every ~0.08-0.1s) for the duration of `iframe_timer`, or toggle `visible` on/off for a harder classic-NES-style flicker — either is driven by `iframe_timer > 0.0`, not by the (shorter) control-lock timer.
6. When `control_lock_timer` hits 0 (0.25s in), transition out of `Hurt` back to `Idle` (if grounded) or `Fall` (if airborne) — **but `iframe_timer` keeps counting down independently and may still have ~0.75s left.** This is intentional: the player regains control well before invulnerability ends, so they can start moving/dodging again while still flickering and immune — this is exactly how MMX damage feels, and is not a bug to "fix" by coupling the two timers together.
7. When `iframe_timer` hits 0, restore `modulate.a = 1.0` (or `visible = true`), re-enable the Hurtbox's `monitoring`, and clear the invulnerability flag.

## Mover Choice

Two real options exist. Presenting both honestly because the tradeoff is genuine, not a solved problem:

**Option A — `CharacterBody2D` + `move_and_slide()`.** Convenient: built-in floor snapping via `floor_snap_length` keeps the character glued to sloped/stepped ground without manual raycasting, and `motion_mode`/platform velocity inheritance gives moving-platform support close to free. The cost: `move_and_slide()`'s internal slide-adjustment logic (it iteratively resolves collisions and can redirect velocity along a surface) can produce a frame of pixel jitter or an unwanted "step" against certain corner geometry (e.g. a character sliding into an inside corner where floor meets wall), and the response can feel slightly "sticky" or imprecise compared to bespoke logic, because you don't have raw, single-collision-per-axis control — the engine is making resolution-order decisions on your behalf.

**Option B — custom mover via `move_and_collide()`** (or fully manual AABB-vs-`TileMapLayer` overlap tests). Frame-tight and fully deterministic: you resolve X-axis collision, then Y-axis collision, explicitly, in an order you control, with no hidden slide heuristics. The cost: you now own floor snapping, one-way platform pass-through, and moving-platform carry yourself — all solved problems, but solved *by you*, in code you maintain.

**Default used by `player_controller.gd`: Option A, `CharacterBody2D`, with a constrained usage pattern:**

- `velocity` is set explicitly from state logic every physics tick — the template never lets `move_and_slide()`'s residual/leftover velocity silently persist or accumulate authority over what the character "wants" to do next tick. Every state block computes the full `velocity` vector it wants, then the dispatcher calls `move_and_slide()` exactly once at the end of `_physics_process`.
- `floor_snap_length` is set once in `_ready()` to a small constant (4-8px is the template default) for stable ground contact over minor bumps/steps without needing manual snapping code.
- Wall detection for gameplay-critical logic (facing direction, WallSlide/WallJump eligibility) does **not** rely on inferring facing from `move_and_slide()`'s slide vectors. The template uses `is_on_wall()` as a coarse gate plus an explicit `RayCast2D` (or `ShapeCast2D`) pointing in the character's current facing direction to confirm which side the wall is on and get a clean surface normal — this avoids the ambiguity of trying to reverse-engineer facing from a slide result.

Rationale: this gets moving-platform support and floor-snap convenience essentially for free, while sidestepping the classic gotchas by never trusting `move_and_slide()`'s internals for anything gameplay-critical beyond "did I land" and "am I generally touching a wall." This is what the flagship template implements.

**When to switch to Option B (the escape hatch):** switch to a custom `move_and_collide()` mover if you need frame-perfect corner-case handling — ledge-grabs that require exact pixel-edge detection, one-pixel-corridor squeezes, or classic Mega Man-style sub-pixel accumulator movement (where velocity is tracked as a fixed-point or accumulated fractional value below 1px/tick for authentic slow-acceleration feel) — or if `move_and_slide()`'s collision-response order produces visible jitter against your specific tile geometry that you can't resolve via `floor_snap_length` or collision shape tuning. Understand this is more code to own for the life of the project: you're trading "Godot maintains this" for "you maintain this, forever, including every new tile-geometry edge case a level designer invents."
