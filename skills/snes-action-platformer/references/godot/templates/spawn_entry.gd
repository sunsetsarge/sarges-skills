## SpawnEntry — one row in a StageData spawn table.
##
## Attach: not attached to a node. This is a custom Resource class, used as
## the element type of StageData.spawn_table (see stage_data.gd). Kept as
## its own class so each spawn gets typed, Inspector-editable fields
## instead of a loosely-typed Dictionary.
##
## Confirm class/property names against your installed Godot 4.x version.
class_name SpawnEntry
extends Resource

## Which enemy to spawn here. Reference an EnemyData .tres — the actual
## enemy scene is whatever scene the spawner script associates with this
## EnemyData (commonly EnemyData could also carry a scene reference; this
## template keeps scene selection in the spawner for flexibility, i.e. the
## same EnemyData stats can be reused by more than one visual scene).
@export var enemy_data: EnemyData

## World-space position (in the stage's coordinate space) this enemy
## spawns at.
@export var position: Vector2 = Vector2.ZERO

## Optional: flags that must ALL be true in WorldFlags for this specific
## spawn to be active. Leave empty for a spawn that's always active
## regardless of world state. This is spawn-level gating, distinct from
## StageData's stage-level world_flags_required (see data-resources.md) —
## a stage can be reachable at all times while still hiding/showing
## individual spawns based on world state (e.g. an enemy that only
## appears after a related boss is defeated).
@export var required_flags: Array[StringName] = []
