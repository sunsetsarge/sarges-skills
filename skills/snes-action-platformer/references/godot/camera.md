# Camera System (Godot 4.3+)

How `templates/camera_controller.gd` implements MMX-style camera behavior: deadzone follow, look-ahead, room-lock, boss-lock, auto-scroll, and pixel snapping.

## Table of Contents

- [Deadzone Follow](#deadzone-follow)
- [Look-Ahead](#look-ahead)
- [Room-Lock via Area2D Triggers](#room-lock-via-area2d-triggers)
- [Boss-Arena Lock](#boss-arena-lock)
- [Auto-Scroll Mode](#auto-scroll-mode)
- [Pixel-Snapping the Camera](#pixel-snapping-the-camera)

## Deadzone Follow

Godot's built-in `Camera2D` has two relevant mechanisms and the template documents both, but commits to the custom one:

- **Built-in**: `position_smoothing_enabled` (lerp the camera toward the target over time instead of snapping instantly) plus `drag_horizontal_enabled`/`drag_vertical_enabled` with drag margins (the camera only starts moving once the target crosses a margin near the edge of the viewport, giving a soft deadzone-like effect). This is quick to set up entirely in the Inspector with no code, and is a reasonable choice for a simpler project.
- **Custom (what the template uses)**: an explicit deadzone `Rect2` defined in camera-local space (e.g. 40x24px centered on screen). Each physics tick, compute the player's position relative to the camera's current position; if the player is inside the deadzone rect, the camera doesn't move at all; if the player has moved outside it, the camera moves just enough to keep the player at the deadzone's edge (not all the way back to center). This gives tighter, more predictable control over exactly how much the player can move before the camera reacts — important for MMX-feel because the built-in drag-margin system's margins are measured from the viewport edges, which conflates "how far from center can the player get" with "how close to the edge of the visible screen," whereas a custom deadzone rect lets you tune those independently and keep the deadzone small and centered regardless of viewport size changes.

The template uses the custom deadzone rect specifically so the deadzone size is a designer-tunable constant independent of viewport/window size, and so look-ahead (below) can offset the deadzone's center rather than fighting the built-in drag-margin math.

## Look-Ahead

When the player is moving fast (running past a speed threshold, or dashing), offset the camera's target point 32-48px (template default: 40px) in the direction the player currently faces or is dashing toward. This reveals more of the level ahead of fast travel, which matters because at dash speed (210 px/s) the player can outrun what a centered camera would show in time to react to it.

The offset is not applied instantly — snapping the deadzone center 40px the instant a dash starts would itself cause a visible camera jerk. Instead it's lerped in over ~0.3-0.5s (template default: 0.4s) using a simple `lerp(current_offset, target_offset, delta / lookahead_time)` each physics tick, so the camera eases toward the offset position as the player accelerates and eases back when they stop/turn around.

## Room-Lock via Area2D Triggers

Place an `Area2D` (collision layer `triggers`, layer 7 per `project-setup.md`'s table) at each room boundary/doorway. On `body_entered` (filtered to the player's collision layer via the Area2D's mask), the trigger calls a method on the camera controller, e.g. `camera.set_room_bounds(limit_left, limit_top, limit_right, limit_bottom)`, which sets `Camera2D`'s built-in `limit_left`/`limit_right`/`limit_top`/`limit_bottom` properties to the new room's bounds.

This is the mechanism MMX uses to "lock" the camera to the current room instead of letting it scroll into off-screen/unfinished art past a level's edge — the built-in limit properties clamp the camera's actual rendered position to stay within the given rectangle, regardless of what the deadzone/look-ahead math would otherwise compute. Each room-transition trigger just swaps which rectangle is active; the deadzone and look-ahead logic keep running underneath, they just can't push the camera past the current limits.

## Boss-Arena Lock

Same trigger mechanism (an Area2D at the boss-arena entrance), but on entry the camera controller also:

- Disables deadzone follow and look-ahead (set an internal `mode` enum to `BOSS_LOCK`, and have the deadzone/lookahead code early-return when in this mode).
- Either hard-centers the camera on the arena's fixed center point, or clamps `limit_*` tightly enough that the arena is exactly the visible area with no scroll room at all in any direction.

Why disable deadzone/look-ahead specifically for boss fights: MMX-style boss arenas are single static rooms by design — the player and boss should always be fully visible with no scrolling, so the camera doesn't need to "follow" anything at all once locked. Leaving deadzone/look-ahead active would let the camera drift slightly as the player dashes around the (usually small) arena, which reads as unwanted camera wobble in a fight where the whole point is a stable, readable view of both combatants.

## Auto-Scroll Mode

A fourth `mode` enum value, `AUTO_SCROLL`, alongside `OFF` (free deadzone-follow, no room limits set), `ROOM_LOCK` (deadzone-follow within current `limit_*` bounds), and `BOSS_LOCK` (described above). In `AUTO_SCROLL` mode, the camera's position advances at a fixed, designer-set `scroll_speed_px_s` (e.g. 60 px/s) in a fixed direction every physics tick, completely independent of the player's position — classic forced-scroll segments (auto-scrolling corridors, escape sequences).

Document both uses this enables:
1. **Escape/pressure sequences**: the scrolling edge is a soft "keep up or fall behind and get cut off" pressure, without necessarily killing the player instantly.
2. **Hard crush hazard**: if the level design pairs auto-scroll with a solid wall or hazard riding at the trailing edge of the screen (or simply "off left edge of camera = instant death"), the player *must* out-pace the scroll or die — this is the classic "auto-scroll shooter stage" hazard pattern. Make sure `scroll_speed_px_s` is tuned comfortably below the player's `dash_speed` combined with `walk_speed` mix if you intend the segment to be beatable without perfect dashing, or intentionally tight against it if you want a tense speed-check segment — pick deliberately, this is a level-feel decision, not a default to leave unconsidered.

## Pixel-Snapping the Camera

The problem: a smoothly-moving or lerped camera position (from `position_smoothing_enabled`, the deadzone's own gradual correction, or the look-ahead lerp) will very often sit at a fractional pixel coordinate, e.g. `camera.global_position.x = 204.63`. Because everything else on screen renders relative to the camera, that fractional camera offset shifts the effective on-screen position of every sprite by a fractional amount too — and as the fraction crosses pixel boundaries frame to frame, pixel art visibly shimmers/wobbles even though the sprites themselves are individually pixel-snapped (per `project-setup.md`'s 2D snap settings), because the *camera's* fractional offset is what's actually misaligning the final composited image.

Two valid fixes, pick one and apply it consistently:

1. **Disable smoothing, snap every tick.** Set `position_smoothing_enabled = false` and instead move the camera's position via your own deadzone/lookahead math, then explicitly `round()` (or `floor()`) the final `global_position.x` and `global_position.y` to the nearest whole pixel before the frame renders (do this at the end of `_physics_process`, after all deadzone/lookahead math for that tick is done). This is simpler to reason about since there's only one place position is ever set.
2. **Keep smoothing, snap only the final result.** If you want Godot's built-in smoothing curve specifically (a different easing feel than a manual lerp), leave `position_smoothing_enabled = true`, but in `_process` (camera visual position can be read-and-corrected post-physics since it's purely a rendering concern at that point) round the camera's *rendered* global position to the nearest integer pixel, without altering the underlying smoothed value the built-in system is tracking internally — i.e. snap a copy used for rendering, not the source-of-truth position driving the smoothing math, or the smoothing curve itself will visibly stair-step.

The template uses approach 1 (manual deadzone/lookahead math + explicit rounding every physics tick) since it already needs custom per-tick position logic for the deadzone rect and look-ahead offset anyway — there's no separate built-in smoothing system to keep in sync with.
