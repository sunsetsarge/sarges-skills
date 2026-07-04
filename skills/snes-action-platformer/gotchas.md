# Gotchas — Hard-Won Pitfalls

Numbered, each with symptom, cause, and fix. Read this before implementing physics, state machines, or the weapon/boss data layer — every one of these has actually broken a build in this genre.

## 1. Pixel-snapping / camera sub-pixel wobble

**Symptom**: sprites shimmer, edges flicker, or single-pixel-wide seams appear between tiles while the camera scrolls, especially at slow scroll speeds.

**Cause**: the camera or a moving transform lands on a fractional (sub-pixel) position at the internal 256x224 resolution, and the integer-scaled display upscale then renders that fractional offset as visibly inconsistent pixel widths across the frame.

**Fix**: snap the camera position (and ideally all rendered transforms) to whole pixels at the internal resolution every frame, and use **integer scale factors only** (2x, 3x, 4x) when upscaling to the display — never a non-integer scale. This is stated as a hard rule in `references/design/game-feel.md`; treat any non-integer scale option in project settings as a bug.

## 2. `move_and_slide` jitter on slopes/steps

**Symptom**: the player's y-position micro-jitters (visibly vibrates) while walking across tile seams, single-tile steps, or slight slope changes, even though horizontal movement looks fine.

**Cause**: Godot's `move_and_slide` (and equivalent slide-based movement in other engines) resolves collision by sliding along a computed collision normal each physics step; on a tile grid with hard seams between tiles of a slightly different height, this can produce a tiny vertical correction every single step, which reads as jitter at 60Hz.

**Fix**: use a dedicated grounded/floor-snap step (`apply_floor_snap()` in Godot 4, or an equivalent explicit "snap to floor height when grounded" pass) separate from the general slide resolution, and prefer a custom X-then-Y axis-separated collision resolution (see `references/design/architecture.md`) over relying on generic slide-vector math for platformer-precision movement. Do not just increase floor snap length blindly — verify it against the actual tile height being used.

## 3. Physics-tick vs frame timing (logic in `_process` drifts)

**Symptom**: gameplay feels inconsistent across different machines/framerates — jump height, dash distance, or coyote-time windows are subtly different depending on display refresh rate or frame drops.

**Cause**: gameplay logic (velocity integration, state machine transitions, buffer timers) was written in a per-rendered-frame callback (`_process` in Godot) instead of the fixed-timestep physics callback, so its effective tick rate is coupled to render framerate rather than a fixed 60Hz.

**Fix**: **all gameplay logic lives in `_physics_process` at a fixed 60Hz tick**, per the input-reading-order rule in `references/design/game-feel.md`. Reserve `_process` strictly for purely cosmetic, non-gameplay-affecting work (e.g., screen-space UI animation that doesn't need frame-perfect reproducibility). Any timer that affects fairness (coyote, jump buffer, i-frames, charge tiers) must be driven off the fixed tick, not `delta` in a variable-rate callback.

## 4. One-way platform drop-through edge cases

**Symptom**: pressing down+jump to drop through a one-way platform sometimes fails to drop, or the player falls through a platform they were merely standing near the edge of (not deliberately dropping through).

**Cause**: one-way platform logic is usually implemented as "ignore collision from below, collide from above," resolved per physics tick — this creates a race between the down+jump input read and the current per-tick collision state, and a naive edge-overlap check (player's collision shape barely overlapping the platform edge) can be misread as "standing on it" or "not standing on it" inconsistently frame to frame.

**Fix**: implement drop-through as an explicit, timed state (e.g., "ignore this specific platform's collision layer for N ticks after down+jump is pressed while grounded on a one-way platform") rather than a per-tick collision-mask toggle recomputed from ambiguous overlap state. Test the specific edge case of standing with only a few pixels of overlap at a platform's edge — this is the exact overlap ratio that breaks naive implementations first.

## 5. Coyote-time + dash-off-ledge momentum interaction (double-dash exploit / lost dash-jump)

**Symptom**: either (a) a player can dash, run off a ledge, and dash again while still inside the coyote window to get an unintended second full-speed dash burst in mid-air, or the opposite bug (b) a player who dashes off a ledge and presses jump within the coyote window gets a plain jump instead of the expected dash-jump, "losing" the dash-jump they should have gotten.

**Cause**: coyote time and dash-carry-into-jump are two separate systems that both check "did the player recently leave the ground" but don't agree on what state to inherit — treating coyote-window-jump as a totally fresh input (bug b) or treating the airborne dash timer as re-armable mid-air (bug a).

**Fix**: state the rule exactly as written in `references/design/game-feel.md`'s "Dash-off-a-ledge edge case" section: a coyote-window jump **inherits whatever horizontal state was active at the moment of leaving the ground** (so a dash-off-ledge + coyote-jump = dash-jump, correctly), but the dash **action itself** (the ability to trigger a new dash) is not re-armed by leaving the ground — only touching ground again (or an air-dash charge, if the design has one, per `references/design/mechanics.md`) re-arms dashing. Coyote time governs the **jump** input's grace window; it must never be read as also re-granting a fresh dash.

## 6. Jump-buffer double-fire

**Symptom**: a single buffered jump press occasionally produces two jumps in a row on landing — the player taps jump once just before landing and gets an unexpected extra hop.

**Cause**: the buffer-consume check (`if grounded-this-tick and buffer-timer-active, fire jump`) runs every tick without clearing the buffer flag immediately upon firing, so if the grounded check remains true for more than one tick after the jump fires (e.g., the jump's upward velocity hasn't been applied yet in evaluation order, or a state-machine re-entry re-reads the same buffer value), it fires again.

**Fix**: clear the buffer timer/flag in the **same tick** the buffered jump is consumed, before any other system that tick can re-read it — treat "consume" as an atomic read-and-clear, not a read followed by a separate clear later in the tick's resolution order (see the fixed input-reading order in `references/design/game-feel.md`). Add a regression test/manual check: land repeatedly while holding jump slightly early and confirm exactly one jump fires per landing.

## 7. I-frame / knockback state traps

**Symptom**: the player gets hit, and either (a) the Hurt state re-triggers repeatedly while the player is still supposedly invincible (visibly flickering but taking knockback/re-entering Hurt on every frame a hazard overlaps them), or (b) knockback shoves the player into a wall and they become stuck, unable to act, for longer than the i-frame window.

**Cause**: two timers are being conflated — the **i-frame timer** (1.0s, governs damage immunity) and the **control-lock timer** (shorter, e.g. 0.25s, governs how long knockback overrides player input) — and the Hurt state itself is allowed to be re-entered by a new collision even while i-frames are active, because the state machine doesn't check invincibility before allowing a Hurt transition.

**Fix**: two explicit rules. First, **Hurt is not re-enterable while the i-frame flag is active** — a new hazard collision during i-frames may still be ignored for damage purposes (which it should be, since i-frames block damage), but it must not re-trigger the Hurt state/animation/knockback a second time. Second, **the control-lock timer is separate from and shorter than the i-frame timer** (see `references/design/game-feel.md`: 0.25s control lock vs 1.0s i-frames) — the player regains input control well before invincibility ends, so a knockback-into-wall situation resolves to "player can act, still flashing/invincible" rather than "player is stuck and vulnerable-looking but actually can't do anything for a full second."

## 8. Charge-state vs locomotion-state conflicts

**Symptom**: holding the fire button to charge a shot, then jumping, dashing, or taking damage, cancels the charge — the player loses charge progress just by moving, which feels broken since nothing in this genre's convention should force that trade-off.

**Cause**: charge state was implemented as a branch inside the locomotion state machine (e.g., a "Charging" state that competes with Idle/Run/Jump/etc.) rather than as an independent parallel system, so any locomotion state transition (which is frequent — jumping, dashing, landing) forces an exit from "Charging" and drops progress.

**Fix**: charge state lives in a **parallel action layer**, resolved independently of the locomotion FSM in the same tick (see step 8 of the input-reading order in `references/design/game-feel.md`) — charging, charge-tier duration tracking, and the charge-aura overlay (see `assets/spritesheet-spec.md`) must never be gated by, or itself gate, which locomotion state (Idle/Run/Jump/Fall/Dash/DashJump/WallSlide/WallJump) the player is currently in. The only things that should cancel a charge are firing the shot, taking damage (Hurt state — a deliberate, documented exception), or death — not jumping, dashing, or landing.

## 9. Weakness-chart data integrity

**Symptom**: late in content development, a boss turns out to have no weapon that's super-effective against it, or a weapon's weakness target doesn't correspond to any boss, or two bosses share the same weakness weapon while a third has none — discovered only when a player (or playtester) tries to plan a stage order and hits a wall.

**Cause**: the 8-archetype weakness cycle (Frost/Flame/Storm/Volt/Stone/Toxin/Blade/Gravity) is defined piecemeal across separate `BossData` and `WeaponData` resources with no central validation, so an authoring mistake in any single resource silently breaks the cycle's completeness.

**Fix**: validate the full cycle at load time (a startup/editor-time check, not just a manual spreadsheet review) — walk every `BossData`'s weakness archetype and every `WeaponData`'s `weakness_target`, confirm a 1:1 bijection across all 8 archetypes, confirm no self-loops (a boss weak to its own reward weapon), and confirm the assignments trace a single connected cycle rather than splitting into sub-cycles or dead ends (see `checklists/new-weapon.md` step 6 for the exact integrity conditions). Fail loudly (editor warning or startup assertion) rather than silently shipping an unbeatable-feeling gap.

## 10. Projectile pool exhaustion

**Symptom**: mid-boss-fight (often exactly when the player is spamming shots at a boss with high uptime, or during a screen full of small enemies), shots silently stop appearing — the player presses fire, animation and SFX play, but no projectile spawns, with no error or warning shown.

**Cause**: the projectile pool (see `checklists/new-weapon.md` step 2) is sized too small for worst-case simultaneous on-screen shots (e.g., max ammo-rate x travel time across the whole screen, times however many weapons/enemies can be firing at once), so a pool `acquire()` call fails and is swallowed silently rather than logged or handled.

**Fix**: size every projectile pool to the **worst realistic case**, not the average case — compute it explicitly (fire rate x max projectile lifetime x number of simultaneous sources, e.g., player + several enemies all firing at max rate) rather than picking a round number by feel. Additionally, **log every acquire failure** during development (a warning is enough; this should never be a hard crash) so an undersized pool is caught in playtesting rather than shipped silently — a silently-dropped shot during a real boss fight is one of the hardest bugs to reproduce from a bug report alone, since the player has no error to describe, just "my shots stopped working sometimes."

## 11. Save / WorldFlags desync

**Symptom**: after a boss defeat (or other major state change), reloading the game shows an inconsistent state — e.g., the reward weapon was granted and usable in the current session, but reloading shows the boss as not-yet-defeated and the weapon gone, or vice versa (weapon missing but boss shown defeated).

**Cause**: multiple systems (WorldFlags write, inventory grant, save-file write) fire at different points across the boss-defeat sequence (death animation, reward jingle, flag set, save write) instead of as one atomic operation, so a crash, forced quit, or even just an unlucky ordering bug between these steps can leave the save file and the WorldFlags state disagreeing with each other.

**Fix**: perform **a single save transaction immediately after boss defeat** that writes the WorldFlag, the weapon grant, and any other end-of-fight state together as one atomic save operation — not scattered writes triggered independently by the death animation finishing, the jingle finishing, and the transition-out-of-arena logic separately. If the target save system can't do true atomic multi-field writes, at minimum batch all the state mutations into memory first, then perform one save call, so a crash before that call leaves the pre-fight state intact rather than a half-updated one.

## 12. TileMapLayer vs deprecated TileMap API

**Symptom**: following older Godot 4.0/4.1-era tutorials or copy-pasted code produces deprecation warnings, or collision/rendering behaves subtly differently than documented, when building stage tilemaps.

**Cause**: Godot 4.3 introduced `TileMapLayer` as the replacement for the older single `TileMap` node (which supported multiple layers within one node); the old `TileMap` node is deprecated and being phased out, but plenty of still-circulating tutorials, forum answers, and even some AI-generated code default to the old API.

**Fix**: use **`TileMapLayer`** (one node per layer, e.g., a separate `TileMapLayer` for background, collision/ground, and foreground-decoration) for all new stage work, per the stage checklist (`checklists/new-stage.md` step 2). If working from an older reference or template, check the Godot version target before copying tilemap code — verify against the current Godot 4 docs, not an older cached tutorial.

## 13. `flip_h` asymmetric hitbox / shoot origin

**Symptom**: after mirroring the player sprite for left-facing, the hitbox is slightly offset from the visible sprite on one facing direction, or projectiles spawn from the wrong side of the character when facing left.

**Cause**: `flip_h` mirrors the **rendered sprite** but does not automatically mirror child node local-space offsets (collision shapes, weapon-muzzle markers) unless those children are explicitly set up to respond to the flip (via negative scale propagation or manual offset negation) — see the pivot/facing rule in `assets/spritesheet-spec.md`.

**Fix**: for the shoot-origin case, follow the fix documented in `assets/spritesheet-spec.md` exactly (mirror the muzzle `Marker2D`'s local X or let it inherit negative-scale propagation, verified visually at both facings). For hitboxes, prefer a **symmetric collision shape** (centered on the sprite's vertical midline) wherever the visual silhouette allows it, so flipping never matters for collision; only asymmetric visual elements (the buster arm) need the explicit per-facing handling.

## 14. `Area2D` signal timing (area_entered during physics flush)

**Symptom**: an `area_entered`/`body_entered` signal handler (e.g., a hazard dealing damage, an item pickup, a hitbox-vs-hurtbox check) occasionally fires twice for what should be a single overlap event, or fires with stale position/state data.

**Cause**: Godot's physics/area signals are emitted during the physics engine's internal collision-processing flush, which can happen at a point in the frame where the responding code reads state (position, active-hit-flags) that hasn't been fully updated for that tick yet, or where a single continuous overlap spanning multiple physics substeps emits the signal more than once if not explicitly deduplicated.

**Fix**: in signal handlers for combat-relevant overlaps (hitbox-vs-hurtbox especially), guard against duplicate processing with an explicit "already processed this hit" flag (cleared appropriately, e.g., on the attack instance being destroyed/reused from the pool — see gotcha #10) rather than assuming one signal emission per logical overlap. Do state-dependent logic (apply damage, grant i-frames) in response to the signal, but re-validate any position/state reads against the current `_physics_process` tick's authoritative state rather than trusting values captured at signal-emission time if there's any ambiguity.

## 15. Audio latency on Windows

**Symptom**: SFX (especially jump, dash, buster shot — the highest-frequency, most timing-sensitive sounds) feel slightly delayed relative to the on-screen action, most noticeable on Windows builds versus the same project running elsewhere.

**Cause**: Windows audio output through the default driver (WASAPI in shared mode, or worse, an older DirectSound path) can introduce tens of milliseconds of output latency that's imperceptible for music but very noticeable for frame-critical action-game SFX like a jump cue.

**Fix**: in Godot's audio driver/export settings, prefer WASAPI in **exclusive mode** or lower the configured audio buffer size (accepting the added risk of audio glitches/underruns on weaker hardware as a tradeoff) for the Windows export target specifically. Test perceived input-to-SFX latency directly (not just "does it play") on the actual target hardware profile before shipping, since this is a platform-specific tuning pass, not a one-time fix that transfers cleanly from a dev machine to every player's setup.

## 16. Integer-scale black bars on odd window sizes

**Symptom**: at certain window sizes (especially user-resized windows, or fullscreen on an uncommon display resolution), the game renders with unexpectedly large black letterbox bars, or the integer-scaled image looks smaller than expected relative to the window.

**Cause**: because upscaling from 256x224 must use an integer scale factor only (see gotcha #1 and `references/design/game-feel.md`), any window size that isn't an exact multiple of 256x224 forces the renderer to pick the next-lower integer scale that fits, leaving a remainder as black bars — this is correct behavior, but if not deliberately designed for, it can look like a bug (e.g., a 1920x1080 window only fits a 4x scale of 224 height with a large leftover, since 1080/224 = 4.8, not a clean multiple).

**Fix**: this is expected and correct, but pair it with either (a) centering the scaled viewport within the window rather than pinning to a corner (an off-center image reads as more obviously "broken" than symmetric letterboxing), or (b) offering a "stretch to fit" toggle in options for players who prefer filling the window over pixel-perfect scaling, clearly labeled as trading pixel accuracy for screen fill. Do not silently default to non-integer stretch to "solve" the black bars — that reintroduces the shimmer problem from gotcha #1.
