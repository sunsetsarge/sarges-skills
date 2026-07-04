## player_controller.gd — flagship SNES-style action-platformer FSM.
##
## Attach to: a CharacterBody2D (the player). Requires child nodes:
##   - CollisionShape2D (sized to your sprite's collision footprint)
##   - A facing RayCast2D named "WallCheckRay" (see _ready(), auto-created
##     if missing so this runs standalone, but prefer placing it yourself
##     in-editor so you can position it precisely at chest height)
##   - Optionally a Sprite2D/AnimatedSprite2D for modulate.a i-frame flicker
##
## Mover choice: CharacterBody2D + move_and_slide(), constrained usage
## pattern (velocity set explicitly every tick, floor_snap_length for
## stable ground contact, wall detection via is_on_wall() + a facing
## raycast rather than inferred from slide vectors). See
## references/godot/player-controller.md's "Mover Choice" section for the
## full tradeoff writeup and when to switch to a custom move_and_collide()
## mover instead.
##
## All gameplay logic runs in _physics_process(delta), never _process(),
## per references/godot/project-setup.md's determinism rule.
##
## Confirm class/property names (especially RayCast2D/ShapeCast2D API and
## CharacterBody2D's floor_snap_length) against your installed Godot 4.x
## version — this targets 4.3+.
extends CharacterBody2D

# ---------------------------------------------------------------------------
# Tunables — canonical default values. Keep these in sync with any other
# doc/template in this skill that references the same mechanic; do not
# invent different numbers for the same tunable in a different file.
# ---------------------------------------------------------------------------

@export var gravity: float = 900.0
@export var walk_speed: float = 90.0
@export var dash_speed: float = 210.0
@export var dash_duration: float = 0.35
@export var jump_velocity: float = -330.0
@export var jump_cut_multiplier: float = 0.45
@export var terminal_fall_speed: float = 450.0
@export var wall_slide_speed: float = 75.0
@export var wall_jump_vx: float = 200.0
@export var wall_jump_vy: float = -300.0
@export var wall_jump_lock_duration: float = 0.1
@export var coyote_time: float = 0.08
@export var jump_buffer_time: float = 0.10
@export var iframe_duration: float = 1.0
@export var knockback_vx: float = 60.0
@export var knockback_lock_duration: float = 0.25
@export var charge_tier_2_time: float = 0.55
@export var charge_tier_3_time: float = 1.1

## Applied to CharacterBody2D's built-in floor_snap_length in _ready():
## how far below the body Godot searches for ground to snap to each tick.
## 4-8px is the sweet spot for a SNES-scale character — enough to ride
## minor bumps/steps without losing floor contact, not so much that it
## snaps across intentional small gaps. (Named differently from the native
## property because GDScript forbids redeclaring an inherited member.)
@export var ground_snap_length: float = 6.0

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

enum State {
	IDLE,
	RUN,
	JUMP,
	FALL,
	DASH,
	DASH_JUMP,
	WALL_SLIDE,
	WALL_JUMP,
	HURT,
	DEAD,
}

var current_state: State = State.IDLE

## +1 = facing right, -1 = facing left. Drives the WallCheckRay direction
## and which side wall-jump/knockback push away from.
var facing: int = 1

# Timers — plain countdown floats, decremented in _update_timers(delta),
# clamped at 0. See references/godot/player-controller.md's "Coyote Timer
# and Jump Buffer" section for how the first two are read.
var coyote_timer: float = 0.0
var jump_buffer_timer: float = 0.0
var dash_timer: float = 0.0
var wall_jump_lock_timer: float = 0.0
var control_lock_timer: float = 0.0
var iframe_timer: float = 0.0

var is_invulnerable: bool = false
var has_dashed_since_ground: bool = false  # simple one-dash-per-airtime gate; remove if unlimited air dash is desired

# Parallel action layer (charge/shoot) — orthogonal to locomotion state.
# See references/godot/player-controller.md's "Parallel Action Layer" section.
var is_charging: bool = false
var charge_time: float = 0.0

# HP is typically owned by GameState (see project-setup.md's autoload
# table), not the controller itself — this local var is a fallback so this
# script is fully standalone/runnable without GameState wired up yet.
@export var max_hp: int = 28
var current_hp: int = max_hp

@onready var wall_check_ray: RayCast2D = _get_or_create_wall_check_ray()
@onready var sprite: CanvasItem = _find_sprite()


func _ready() -> void:
	floor_snap_length = ground_snap_length  # apply tunable to CharacterBody2D's native snap property
	current_state = State.IDLE


func _physics_process(delta: float) -> void:
	_update_timers(delta)
	_update_facing_and_wall_ray()
	_update_action_layer(delta)

	match current_state:
		State.IDLE:
			_state_idle(delta)
		State.RUN:
			_state_run(delta)
		State.JUMP:
			_state_jump(delta)
		State.FALL:
			_state_fall(delta)
		State.DASH:
			_state_dash(delta)
		State.DASH_JUMP:
			_state_dash_jump(delta)
		State.WALL_SLIDE:
			_state_wall_slide(delta)
		State.WALL_JUMP:
			_state_wall_jump(delta)
		State.HURT:
			_state_hurt(delta)
		State.DEAD:
			_state_dead(delta)

	move_and_slide()

	if is_on_floor():
		coyote_timer = coyote_time
		has_dashed_since_ground = false


# ---------------------------------------------------------------------------
# Timers
# ---------------------------------------------------------------------------

func _update_timers(delta: float) -> void:
	coyote_timer = maxf(coyote_timer - delta, 0.0)
	dash_timer = maxf(dash_timer - delta, 0.0)
	wall_jump_lock_timer = maxf(wall_jump_lock_timer - delta, 0.0)
	control_lock_timer = maxf(control_lock_timer - delta, 0.0)

	if iframe_timer > 0.0:
		iframe_timer = maxf(iframe_timer - delta, 0.0)
		if sprite:
			# Flicker: toggle visibility on a fixed interval while i-frames
			# are active. fmod against a short period gives an on/off square
			# wave without needing a separate Timer node.
			sprite.visible = fmod(iframe_timer, 0.16) > 0.08
		if iframe_timer == 0.0:
			is_invulnerable = false
			if sprite:
				sprite.visible = true

	if Input.is_action_just_pressed("jump"):
		jump_buffer_timer = jump_buffer_time
	else:
		jump_buffer_timer = maxf(jump_buffer_timer - delta, 0.0)


func _can_jump() -> bool:
	return is_on_floor() or coyote_timer > 0.0


func _wants_jump() -> bool:
	return Input.is_action_just_pressed("jump") or jump_buffer_timer > 0.0


func _consume_jump_buffer() -> void:
	jump_buffer_timer = 0.0
	coyote_timer = 0.0


# ---------------------------------------------------------------------------
# Facing / wall detection
# ---------------------------------------------------------------------------

func _update_facing_and_wall_ray() -> void:
	var input_dir: float = Input.get_axis("move_left", "move_right")
	if input_dir != 0.0:
		facing = signi(input_dir)
	wall_check_ray.target_position = Vector2(10.0 * facing, 0.0)
	wall_check_ray.force_raycast_update()


## True if is_on_wall() AND the facing raycast confirms a wall directly in
## the facing direction. Using both avoids relying on move_and_slide()'s
## slide-vector inference for gameplay-critical wall-jump/wall-slide
## eligibility — see player-controller.md's Mover Choice section.
func _touching_wall_in_facing_direction() -> bool:
	return is_on_wall() and wall_check_ray.is_colliding()


func _get_or_create_wall_check_ray() -> RayCast2D:
	var existing: Node = get_node_or_null("WallCheckRay")
	if existing is RayCast2D:
		return existing
	var ray := RayCast2D.new()
	ray.name = "WallCheckRay"
	ray.target_position = Vector2(10.0, 0.0)
	ray.enabled = true
	add_child(ray)
	return ray


func _find_sprite() -> CanvasItem:
	for child in get_children():
		if child is Sprite2D or child is AnimatedSprite2D:
			return child
	return null


# ---------------------------------------------------------------------------
# Parallel action layer: charge / shoot (see player-controller.md)
# ---------------------------------------------------------------------------

func _update_action_layer(delta: float) -> void:
	# Shooting/charging is orthogonal to locomotion — it ticks every frame
	# regardless of current_state, EXCEPT while Hurt or Dead, where the
	# player shouldn't be able to act at all.
	if current_state == State.HURT or current_state == State.DEAD:
		is_charging = false
		charge_time = 0.0
		return

	if Input.is_action_pressed("shoot"):
		is_charging = true
		charge_time += delta
	elif Input.is_action_just_released("shoot"):
		_fire_shot(charge_time)
		is_charging = false
		charge_time = 0.0


## Determines charge tier and fires. Actual projectile acquisition should
## go through a ProjectilePool (see templates/projectile_pool.gd) and read
## damage/cooldown/ammo off the equipped WeaponData resource (see
## templates/weapon_data.gd and references/godot/combat.md's weapon flow).
## This is left as a signal so the controller doesn't need a hard
## dependency on WeaponSystem/ProjectilePool wiring to be standalone.
signal shot_fired(charge_tier: int)

func _fire_shot(held_time: float) -> void:
	var tier: int = 1
	if held_time >= charge_tier_3_time:
		tier = 3
	elif held_time >= charge_tier_2_time:
		tier = 2
	shot_fired.emit(tier)


# ---------------------------------------------------------------------------
# Locomotion states
# ---------------------------------------------------------------------------

func _apply_gravity(delta: float) -> void:
	velocity.y = minf(velocity.y + gravity * delta, terminal_fall_speed)


func _state_idle(_delta: float) -> void:
	velocity.x = 0.0
	if not is_on_floor():
		_change_state(State.FALL)
		return

	var input_dir: float = Input.get_axis("move_left", "move_right")
	if input_dir != 0.0:
		_change_state(State.RUN)
		return
	if Input.is_action_just_pressed("dash"):
		_change_state(State.DASH)
		return
	if _can_jump() and _wants_jump():
		_consume_jump_buffer()
		_change_state(State.JUMP)


func _state_run(_delta: float) -> void:
	var input_dir: float = Input.get_axis("move_left", "move_right")
	velocity.x = input_dir * walk_speed

	if not is_on_floor():
		_change_state(State.FALL)
		return
	if input_dir == 0.0:
		_change_state(State.IDLE)
		return
	if Input.is_action_just_pressed("dash"):
		_change_state(State.DASH)
		return
	if _can_jump() and _wants_jump():
		_consume_jump_buffer()
		_change_state(State.JUMP)


func _state_jump(delta: float) -> void:
	var input_dir: float = Input.get_axis("move_left", "move_right")
	velocity.x = input_dir * walk_speed
	_apply_gravity(delta)

	# Variable jump height: cutting the ascent early scales vy toward 0
	# rather than zeroing it outright, which keeps a small hop feeling
	# responsive instead of abruptly clipped.
	if Input.is_action_just_released("jump") and velocity.y < 0.0:
		velocity.y *= jump_cut_multiplier

	if _touching_wall_in_facing_direction() and input_dir != 0.0:
		_change_state(State.WALL_SLIDE)
		return
	if velocity.y >= 0.0:
		_change_state(State.FALL)


func _state_fall(delta: float) -> void:
	var input_dir: float = Input.get_axis("move_left", "move_right")
	velocity.x = input_dir * walk_speed
	_apply_gravity(delta)

	if is_on_floor():
		_change_state(State.RUN if input_dir != 0.0 else State.IDLE)
		return
	if _touching_wall_in_facing_direction() and input_dir != 0.0:
		_change_state(State.WALL_SLIDE)
		return
	if not has_dashed_since_ground and Input.is_action_just_pressed("dash"):
		_change_state(State.DASH)
		return
	if _can_jump() and _wants_jump():
		_consume_jump_buffer()
		_change_state(State.JUMP)


func _state_dash(delta: float) -> void:
	velocity.x = float(facing) * dash_speed
	# Suppress gravity only while grounded, so a ground-dash stays flat but
	# an air-dash still arcs slightly — matches MMX dash-jump feel per
	# player-controller.md's Dash-Jump Momentum Carry section.
	if is_on_floor():
		velocity.y = 0.0
	else:
		_apply_gravity(delta)

	if _can_jump() and _wants_jump():
		_consume_jump_buffer()
		_change_state(State.DASH_JUMP)
		return

	if dash_timer <= 0.0:
		if is_on_floor():
			_change_state(State.IDLE if Input.get_axis("move_left", "move_right") == 0.0 else State.RUN)
		else:
			_change_state(State.FALL)


func _state_dash_jump(delta: float) -> void:
	# Momentum carry: velocity.x was preset to the dash's speed/direction on
	# _enter_state and is NOT force-decayed here — normal air-control input
	# can override it, but nothing actively pulls it back toward walk_speed.
	# See player-controller.md's Dash-Jump Momentum Carry section for the
	# harder-decay alternative (lerp toward walk_speed over air time) if a
	# project wants that instead.
	var input_dir: float = Input.get_axis("move_left", "move_right")
	if input_dir != 0.0:
		velocity.x = input_dir * dash_speed  # steering still lets the player redirect at full speed rather than snapping to walk_speed
	_apply_gravity(delta)

	if Input.is_action_just_released("jump") and velocity.y < 0.0:
		velocity.y *= jump_cut_multiplier

	if _touching_wall_in_facing_direction() and input_dir != 0.0:
		_change_state(State.WALL_SLIDE)
		return
	if velocity.y >= 0.0:
		_change_state(State.FALL)


func _state_wall_slide(delta: float) -> void:
	velocity.x = 0.0
	_apply_gravity(delta)
	velocity.y = minf(velocity.y, wall_slide_speed)

	var input_dir: float = Input.get_axis("move_left", "move_right")

	if is_on_floor():
		_change_state(State.IDLE)
		return
	if not _touching_wall_in_facing_direction() or input_dir == 0.0:
		_change_state(State.FALL)
		return
	if Input.is_action_just_pressed("jump") or jump_buffer_timer > 0.0:
		jump_buffer_timer = 0.0
		_change_state(State.WALL_JUMP)


func _state_wall_jump(delta: float) -> void:
	_apply_gravity(delta)

	if Input.is_action_just_released("jump") and velocity.y < 0.0:
		velocity.y *= jump_cut_multiplier

	# Input lock: horizontal input is deliberately ignored for
	# wall_jump_lock_duration so the outward wall-jump velocity actually
	# carries the character clear of the wall before the player's own held
	# "into the wall" input can fight it. See player-controller.md's States
	# section for the full rationale.
	if wall_jump_lock_timer <= 0.0:
		var input_dir: float = Input.get_axis("move_left", "move_right")
		if input_dir != 0.0:
			velocity.x = input_dir * walk_speed

	if _touching_wall_in_facing_direction() and wall_jump_lock_timer <= 0.0:
		var input_dir2: float = Input.get_axis("move_left", "move_right")
		if input_dir2 != 0.0:
			_change_state(State.WALL_SLIDE)
			return
	if velocity.y >= 0.0:
		_change_state(State.FALL)


func _state_hurt(_delta: float) -> void:
	# velocity was set once on _enter_state (knockback) and is left alone
	# here — control_lock_timer gates when input regains authority.
	if control_lock_timer <= 0.0:
		_change_state(State.IDLE if is_on_floor() else State.FALL)


func _state_dead(_delta: float) -> void:
	velocity.x = 0.0
	velocity.y = minf(velocity.y + gravity * _delta, terminal_fall_speed)
	# Terminal state — an external respawn/reset call (from a checkpoint
	# reload driven by SaveManager) is expected to reset current_hp,
	# position, and current_state back to IDLE. Nothing in this script
	# exits DEAD on its own.


# ---------------------------------------------------------------------------
# State transition dispatcher
# ---------------------------------------------------------------------------

func _change_state(next: State) -> void:
	if next == current_state:
		return
	_exit_state(current_state, next)
	var prev: State = current_state
	current_state = next
	_enter_state(next, prev)


func _enter_state(state: State, _prev: State) -> void:
	match state:
		State.DASH:
			dash_timer = dash_duration
			has_dashed_since_ground = true
		State.DASH_JUMP:
			# Momentum carry: seed vertical velocity like a normal jump but
			# leave velocity.x at whatever the dash already had — do NOT
			# recompute it from walk_speed here.
			velocity.y = jump_velocity
		State.JUMP:
			velocity.y = jump_velocity
		State.WALL_JUMP:
			velocity.x = -float(facing) * wall_jump_vx  # away from the wall, opposite current facing
			velocity.y = wall_jump_vy
			wall_jump_lock_timer = wall_jump_lock_duration
			facing = -facing
		State.HURT:
			pass  # velocity set by take_damage() before _change_state(HURT) is called
		State.DEAD:
			pass


func _exit_state(_state: State, _next: State) -> void:
	pass  # reserved for cleanup hooks (e.g. stopping a dash trail particle) as states are extended


# ---------------------------------------------------------------------------
# Damage entry point — called by this player's Hurtbox (see
# templates/hurtbox.gd) via its hit_taken signal.
# ---------------------------------------------------------------------------

func take_damage(amount: int, source_position: Vector2, _weapon_id: StringName) -> void:
	if is_invulnerable or current_state == State.DEAD:
		return

	current_hp = maxi(current_hp - amount, 0)

	var away_dir: float = signf(global_position.x - source_position.x)
	if away_dir == 0.0:
		away_dir = -float(facing)  # fallback if directly on top of the source
	velocity.x = away_dir * knockback_vx
	velocity.y = 0.0

	control_lock_timer = knockback_lock_duration
	iframe_timer = iframe_duration
	is_invulnerable = true

	if current_hp <= 0:
		_change_state(State.DEAD)
	else:
		_change_state(State.HURT)
