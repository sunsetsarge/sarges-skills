## hitbox.gd — deals damage. Attach to an Area2D.
##
## Attach to: an Area2D used either as a standalone attack hitbox (melee
## swing, projectile) or as a child of a projectile root (see
## projectile.gd, which assumes exactly this node as a child). Set its
## collision layer to "player_attack" (3) or "enemy_attack" (5), and its
## collision mask to the opposing team's Hurtbox layer ("enemy" (4) or
## "player" (2) respectively). See references/godot/project-setup.md's
## collision layer/mask table and references/godot/combat.md's
## Hitbox/Hurtbox Pattern section.
##
## Reusable for both player_attack-vs-enemy and enemy_attack-vs-player by
## setting `team` appropriately — the team-check logic below is identical
## either way.
##
## Confirm class/property names against your installed Godot 4.x version.
extends Area2D

enum Team { PLAYER, ENEMY }

## Team this Hitbox belongs to — used to confirm it's only ever damaging
## an OPPOSING Hurtbox, even if collision masks are accidentally
## misconfigured for some reason (defense in depth, not the primary gate —
## the layer/mask setup in project-setup.md's table is the primary gate).
@export var team: Team = Team.PLAYER

@export var damage: int = 1

## StringName identifying which weapon/attack this Hitbox represents —
## passed through to take_damage() so a Hurtbox/boss script can check it
## against BossData.weakness_weapon_id for bonus damage (see
## combat.md's weapon-system flow, step 9).
@export var weapon_id: StringName = &""

## If true, this Hitbox deactivates itself (monitoring = false) after its
## first successful hit — appropriate for a single-use melee swing or a
## projectile's Hitbox (projectile.gd calls release() on hit anyway, but
## setting this true too avoids a projectile hitting the same target twice
## in the single physics tick before release() takes effect). Leave false
## for a persistent contact-damage area that should keep hitting on every
## fresh (non-i-framed) overlap.
@export var one_shot: bool = false

var _consumed: bool = false


func _ready() -> void:
	monitoring = true
	area_entered.connect(_on_area_entered)
	body_entered.connect(_on_body_entered)


func _on_area_entered(area: Area2D) -> void:
	_try_hit(area)


func _on_body_entered(body: Node2D) -> void:
	# Supports Hurtboxes implemented as a body-layer Area2D check too, in
	# case a project's enemy Hurtbox is attached directly to a
	# CharacterBody2D/StaticBody2D rather than a separate Area2D child.
	if body.has_method("take_damage"):
		_try_hit(body)


func _try_hit(other: Node) -> void:
	if _consumed:
		return
	if not other.has_method("take_damage"):
		return
	if "team" in other and other.team == team:
		return  # team-check: never damage our own team's Hurtbox

	var knockback_dir: Vector2 = Vector2.ZERO
	if other is Node2D:
		knockback_dir = (other.global_position - global_position)
		if knockback_dir.length() > 0.0:
			knockback_dir = knockback_dir.normalized()

	other.take_damage(damage, knockback_dir, weapon_id)

	if one_shot:
		_consumed = true
		monitoring = false
