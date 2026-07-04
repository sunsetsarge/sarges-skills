## projectile.gd — pooled projectile. Attach to the root Area2D of a
## projectile scene.
##
## Scene shape assumed:
##   Area2D (this script)
##     CollisionShape2D
##     Hitbox (Area2D with hitbox.gd attached — see hitbox.gd)
##     Sprite2D / AnimatedSprite2D (visual)
##
## This node is never instantiate()'d or queue_free()'d during gameplay —
## it is preallocated and recycled by a ProjectilePool (see
## projectile_pool.gd). WeaponSystem code calls ProjectilePool.acquire(),
## configures the returned instance's speed/damage/team/lifetime, then
## activates it.
##
## Confirm class/property names against your installed Godot 4.x version.
extends Area2D

enum Team { PLAYER, ENEMY }

@export var speed: float = 240.0
@export var damage: int = 1
@export var team: Team = Team.PLAYER
@export var lifetime: float = 2.0

## Direction this projectile travels, set by whoever calls acquire() —
## normalized by _activate() if not already.
var direction: Vector2 = Vector2.RIGHT

## Set by ProjectilePool on acquire() so this instance can call back to
## release itself without the pool needing to poll every active instance.
var owning_pool: Node = null

var _lifetime_remaining: float = 0.0
var _active: bool = false

@onready var _hitbox: Area2D = get_node_or_null("Hitbox")


func _ready() -> void:
	monitoring = false
	set_physics_process(false)
	visible = false
	if _hitbox:
		_hitbox.monitoring = false
		# Propagate this projectile's team/damage/weapon_id to its Hitbox
		# child so callers only need to configure the projectile, not both
		# nodes separately.
		if "team" in _hitbox:
			_hitbox.team = team
		if "damage" in _hitbox:
			_hitbox.damage = damage


## Called by ProjectilePool.acquire() (or directly by WeaponSystem code)
## to configure and turn on a previously-inactive instance.
func activate(from_position: Vector2, fire_direction: Vector2, projectile_team: Team, projectile_damage: int, weapon_id: StringName = &"") -> void:
	global_position = from_position
	direction = fire_direction.normalized() if fire_direction.length() > 0.0 else Vector2.RIGHT
	team = projectile_team
	damage = projectile_damage
	_lifetime_remaining = lifetime
	_active = true

	if _hitbox:
		_hitbox.team = team
		_hitbox.damage = damage
		_hitbox.weapon_id = weapon_id
		_hitbox.monitoring = true

	monitoring = true
	visible = true
	set_physics_process(true)


func _physics_process(delta: float) -> void:
	if not _active:
		return

	global_position += direction * speed * delta

	_lifetime_remaining -= delta
	if _lifetime_remaining <= 0.0:
		_release()
		return

	if _is_off_screen():
		_release()


func _is_off_screen() -> bool:
	var viewport_rect: Rect2 = get_viewport_rect()
	# get_viewport_rect() is in viewport-local coordinates; a project using
	# a moving camera should compare against camera-relative bounds
	# instead — this is a simple, commonly-good-enough default that works
	# whenever the projectile's canvas layer matches the camera's view.
	var screen_pos: Vector2 = get_global_transform_with_canvas().origin
	var margin: float = 32.0
	return (
		screen_pos.x < -margin
		or screen_pos.y < -margin
		or screen_pos.x > viewport_rect.size.x + margin
		or screen_pos.y > viewport_rect.size.y + margin
	)


## Called on hit by this projectile's Hitbox reporting success (wire the
## Hitbox's hit-confirmation back here if using one_shot on the Hitbox —
## simplest approach: set the Hitbox's one_shot = true and additionally
## connect its area_entered/body_entered signals, or just call this
## directly from wherever confirms the hit).
func on_hit_confirmed() -> void:
	_release()


func _release() -> void:
	_active = false
	monitoring = false
	visible = false
	set_physics_process(false)
	if _hitbox:
		_hitbox.monitoring = false

	if owning_pool and owning_pool.has_method("release"):
		owning_pool.release(self)
