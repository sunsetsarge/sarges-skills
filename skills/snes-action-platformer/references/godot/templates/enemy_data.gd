## EnemyData — data-driven enemy definition.
##
## Attach: not attached to a node. This is a custom Resource class.
## Usage: New Resource > "EnemyData" in the Inspector, fill in fields, save
## as e.g. "enemy_grunt_walker.tres". An enemy scene's script reads this
## resource (via an @export var data: EnemyData field) for its stats rather
## than hardcoding hp/damage/drops per enemy scene.
##
## Drop table entries use the separate DropEntry resource class (see
## drop_entry.gd in this same templates/ folder) — Godot 4 only allows one
## class_name declaration per script file, so the nested drop-row type
## lives in its own file rather than inline here.
##
## Confirm class/property names against your installed Godot 4.x version.
class_name EnemyData
extends Resource

## Enemy max HP.
@export var hp: int = 10

## Damage dealt on player contact for simple touch-damage enemies (see
## references/godot/combat.md's Contact Damage section). Enemies that use a
## full Hitbox for a distinct attack instead of body contact can leave this
## at 0 and drive damage entirely from the Hitbox's own damage field.
@export var contact_damage: int = 1

## Hook key looked up by an EnemyAI / behavior-tree node to select this
## enemy's movement/attack behavior. Not code itself — just an id an AI
## dispatcher switches on (e.g. "walk_patrol", "flyer_sine", "turret_aim").
@export var behavior_id: StringName = &"walk_patrol"

## Drop table rolled on death. Array of DropEntry sub-resources (see
## drop_entry.gd) — each entry is an independent chance roll, not a
## normalized distribution. A drop-roller script loops every entry and
## rolls each independently against randf() < entry.chance.
@export var drop_table: Array[DropEntry] = []

## Score/points awarded on kill, if the project tracks a score system.
@export var score: int = 100

## Freeform tags other systems can check membership against, e.g.
## "flying" (skips ground-only hazards), "armored" (halves non-charged
## damage), "boss_minion" (excluded from stage clear-count requirements).
@export var flags: Array[StringName] = []
