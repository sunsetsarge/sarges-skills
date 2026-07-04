## camera_controller.gd — MMX-style room-lock/deadzone/lookahead camera.
##
## Attach to: a Camera2D node directly (this script extends Camera2D). Set
## this camera Current, and set its "target" export to the player's Node2D
## (or call set_target() from your player-spawn code).
##
## Room-lock triggers: place Area2D nodes at room boundaries on the
## "triggers" collision layer (layer 7, see project-setup.md's layer
## table), connect their body_entered signal to call
## set_room_bounds(...) on this camera.
##
## Pixel snapping: this script disables position_smoothing_enabled and
## does its own deadzone/lookahead math manually every physics tick, then
## rounds the final position to the nearest integer pixel before it's used
## for rendering. See references/godot/camera.md's "Pixel-Snapping the
## Camera" section for why this is necessary and the alternative approach
## (keep built-in smoothing, snap only a rendering copy) if you'd rather
## use Camera2D's smoothing curve.
##
## Confirm class/property names against your installed Godot 4.x version.
extends Camera2D

enum Mode {
	OFF,        ## free deadzone-follow, no room limits enforced
	ROOM_LOCK,  ## deadzone-follow within current limit_* bounds
	BOSS_LOCK,  ## deadzone/lookahead disabled, hard-centered on arena
	AUTO_SCROLL,## advances at a fixed px/s regardless of player position
}

@export var mode: Mode = Mode.OFF

## The node this camera follows (typically the player). Assign in-editor
## or via set_target().
@export var target: Node2D

## Deadzone rect size in camera-local pixels — the player can move this
## far from camera-center before the camera starts correcting. Kept small
## and centered per camera.md's rationale for using a custom rect instead
## of Camera2D's built-in drag margins.
@export var deadzone_size: Vector2 = Vector2(40.0, 24.0)

## How many px the look-ahead offset shifts toward the facing/dash
## direction (canonical range 32-48px; default 40).
@export var lookahead_distance: float = 40.0

## Seconds for the look-ahead offset to lerp fully in (or back out).
@export var lookahead_time: float = 0.4

## Auto-scroll speed in px/s, used only when mode == AUTO_SCROLL.
@export var auto_scroll_speed: float = 60.0

## Auto-scroll direction (normalized on use); default scrolls rightward.
@export var auto_scroll_direction: Vector2 = Vector2.RIGHT

var _lookahead_offset: Vector2 = Vector2.ZERO
var _camera_pos: Vector2 = Vector2.ZERO


func _ready() -> void:
	# This script owns pixel-snapped positioning manually — disable the
	# built-in smoothing so it can't fight the manual math below.
	position_smoothing_enabled = false
	if target:
		_camera_pos = target.global_position
		global_position = _camera_pos


func set_target(new_target: Node2D) -> void:
	target = new_target
	_camera_pos = target.global_position


## Called by a room-boundary Area2D's body_entered handler. Sets this
## camera into ROOM_LOCK mode with the given bounds.
func set_room_bounds(left: float, top: float, right: float, bottom: float) -> void:
	mode = Mode.ROOM_LOCK
	limit_left = int(left)
	limit_top = int(top)
	limit_right = int(right)
	limit_bottom = int(bottom)


## Called by a boss-arena entrance trigger. Locks the camera to the arena
## bounds with no deadzone/lookahead scroll at all.
func set_boss_arena(left: float, top: float, right: float, bottom: float) -> void:
	mode = Mode.BOSS_LOCK
	limit_left = int(left)
	limit_top = int(top)
	limit_right = int(right)
	limit_bottom = int(bottom)
	_lookahead_offset = Vector2.ZERO


func start_auto_scroll(speed_px_s: float, direction: Vector2) -> void:
	mode = Mode.AUTO_SCROLL
	auto_scroll_speed = speed_px_s
	auto_scroll_direction = direction.normalized()


func _physics_process(delta: float) -> void:
	match mode:
		Mode.OFF, Mode.ROOM_LOCK:
			_update_deadzone_follow(delta)
			_update_lookahead(delta)
		Mode.BOSS_LOCK:
			_update_boss_lock()
		Mode.AUTO_SCROLL:
			_update_auto_scroll(delta)

	# Pixel-snap: round the final camera position to the nearest whole
	# pixel every tick before it's used for rendering, per camera.md's
	# Pixel-Snapping section. This is what prevents sub-pixel shimmer on
	# every sprite composited relative to this camera.
	global_position = Vector2(roundf(_camera_pos.x), roundf(_camera_pos.y))


func _update_deadzone_follow(_delta: float) -> void:
	if not target:
		return
	var target_pos: Vector2 = target.global_position + _lookahead_offset
	var delta_to_target: Vector2 = target_pos - _camera_pos

	var half_size: Vector2 = deadzone_size * 0.5
	var correction: Vector2 = Vector2.ZERO

	if delta_to_target.x > half_size.x:
		correction.x = delta_to_target.x - half_size.x
	elif delta_to_target.x < -half_size.x:
		correction.x = delta_to_target.x + half_size.x

	if delta_to_target.y > half_size.y:
		correction.y = delta_to_target.y - half_size.y
	elif delta_to_target.y < -half_size.y:
		correction.y = delta_to_target.y + half_size.y

	_camera_pos += correction


func _update_lookahead(delta: float) -> void:
	if not target:
		return
	# Facing direction is read off the target if it exposes a `facing`
	# int property (player_controller.gd does); fall back to velocity
	# direction, then to no offset.
	var direction: float = 0.0
	if "facing" in target:
		direction = float(target.facing)
	elif "velocity" in target:
		direction = signf(target.velocity.x)

	var target_offset: Vector2 = Vector2(direction * lookahead_distance, 0.0)
	var lerp_weight: float = clampf(delta / lookahead_time, 0.0, 1.0)
	_lookahead_offset = _lookahead_offset.lerp(target_offset, lerp_weight)


func _update_boss_lock() -> void:
	var center: Vector2 = Vector2(
		(limit_left + limit_right) / 2.0,
		(limit_top + limit_bottom) / 2.0
	)
	_camera_pos = center


func _update_auto_scroll(delta: float) -> void:
	_camera_pos += auto_scroll_direction * auto_scroll_speed * delta
