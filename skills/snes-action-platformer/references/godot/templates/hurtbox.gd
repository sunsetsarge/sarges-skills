## hurtbox.gd — receives damage. Attach to an Area2D.
##
## Attach to: an Area2D child of the player or enemy body. Set its
## collision layer to "player" (2) for a player Hurtbox, or "enemy" (4) for
## an enemy Hurtbox — set its collision mask to whichever opposing
## attack layer(s) it should react to ("enemy_attack" (5) for a player
## Hurtbox, "player_attack" (3) for an enemy Hurtbox). See
## references/godot/project-setup.md's collision layer/mask table and
## references/godot/combat.md's Hitbox/Hurtbox Pattern section.
##
## Requires a CollisionShape2D sibling/child sized to the hurtbox area.
##
## Confirm class/property names against your installed Godot 4.x version.
extends Area2D

## Team this Hurtbox belongs to. A Hitbox only calls take_damage() on a
## Hurtbox whose team differs from its own — see hitbox.gd's team-check.
enum Team { PLAYER, ENEMY }
@export var team: Team = Team.PLAYER

## Seconds of invulnerability after taking damage (canonical default 1.0s).
@export var iframe_duration: float = 1.0

## Emitted whenever damage is actually applied (not while invulnerable),
## so the owning controller (player_controller.gd, or an enemy's own
## script) can react — enter a Hurt state, flash a sprite, play an SFX.
signal hit_taken(amount: int, source_position: Vector2, weapon_id: StringName)

var is_invulnerable: bool = false
var _iframe_timer: float = 0.0


func _ready() -> void:
	monitoring = true


func _physics_process(delta: float) -> void:
	if _iframe_timer > 0.0:
		_iframe_timer = maxf(_iframe_timer - delta, 0.0)
		if _iframe_timer == 0.0:
			is_invulnerable = false
			monitoring = true  # re-enable overlap detection now that i-frames ended


## Call this from a Hitbox's area_entered handler (see hitbox.gd) or
## directly from a contact-damage script. knockback_dir should be a
## normalized-or-not direction vector pointing AWAY from the damage
## source — this script does not compute knockback direction itself,
## since the caller (Hitbox) already knows the relative position.
func take_damage(amount: int, knockback_dir: Vector2, weapon_id: StringName) -> void:
	if is_invulnerable:
		return

	is_invulnerable = true
	_iframe_timer = iframe_duration
	# Turning monitoring off is the actual mechanism that prevents repeat
	# overlaps (e.g. a stationary contact-damage enemy) from re-triggering
	# take_damage every physics tick during i-frames — see combat.md's
	# I-Frames section for why the flag alone isn't sufficient.
	monitoring = false

	var source_position: Vector2 = global_position - knockback_dir
	hit_taken.emit(amount, source_position, weapon_id)
