## StageData — data-driven stage definition.
##
## Attach: not attached to a node. This is a custom Resource class.
## Usage: New Resource > "StageData" in the Inspector, fill in fields, save
## as e.g. "stage_01_intro.tres". A stage-loading autoload/scene reads this
## resource to know which tilemap scene to load, what music to play, what
## enemies to spawn where, and which world-flag-gated variants apply.
##
## Assumes a WorldFlags autoload singleton exists (see
## references/godot/project-setup.md's Autoload Singletons section and
## references/godot/data-resources.md's StageData <-> WorldFlags section)
## exposing at minimum:
##   func has_flag(flag_name: StringName) -> bool
##   func set_flag(flag_name: StringName, value: bool) -> void
##
## Confirm class/property names against your installed Godot 4.x version.
class_name StageData
extends Resource

## The stage's tilemap/level scene (should contain a TileMapLayer plus any
## static geometry, triggers, and hazards for this stage).
@export var tilemap_scene: PackedScene

## Background music for this stage. AudioStream (not a String path) so the
## Inspector gives a direct, type-checked audio resource picker; the
## AudioManager autoload (see project-setup.md) is expected to crossfade
## into this stream on stage load.
@export var music: AudioStream

## Every enemy spawn in this stage. See spawn_entry.gd — each entry is an
## EnemyData reference + a position + optional per-spawn flag gating.
@export var spawn_table: Array[SpawnEntry] = []

## Checkpoint positions in stage order. SaveManager records the index of
## the last-touched checkpoint; on death/reload the player resumes at
## checkpoint_positions[index] rather than stage start.
@export var checkpoint_positions: Array[Vector2] = []

## Freeform per-stage tuning values a stage's gimmick scripts read at
## runtime — e.g. {"conveyor_speed": 80.0, "wind_force": 40.0}. Kept as a
## Dictionary (rather than more nested Resource classes) because gimmick
## needs vary wildly per stage and a flat key/value bag is the pragmatic
## choice here; a project with many recurring gimmick types may want to
## promote frequently-reused keys into a proper nested Resource later.
@export var gimmick_config: Dictionary = {}

## Flags this stage sets in WorldFlags when its boss (or stage-clear
## condition) is defeated/completed. Applied by whatever boss-defeat or
## stage-clear script calls WorldFlags.set_flag() for each entry here.
@export var world_flags_set: Array[StringName] = []

## Flags that must ALL be true in WorldFlags before this stage as a whole
## is selectable/enterable from the stage-select or overworld. Leave empty
## for a stage always available from the start.
@export var world_flags_required: Array[StringName] = []

## Maps a WorldFlags flag name to a variant key, e.g.
## {"boss_heat_defeated": "shortcut_open"}. Stage-load logic (or the
## tilemap_scene itself) can check get_active_variant() below to decide
## which tile/door/hazard variant to show. See data-resources.md's
## StageData <-> WorldFlags section for the full explanation.
@export var world_flag_variants: Dictionary = {}


## Returns the subset of spawn_table whose required_flags are all
## currently true in WorldFlags. Call this from the stage's spawner script
## at stage load (and again after any WorldFlags change if the stage
## supports live-updating spawns, e.g. a shortcut door opening mid-stage).
##
## WorldFlags is assumed to be an autoload singleton — reference it here
## by its autoload name directly, which is valid GDScript once the
## autoload is registered in Project Settings.
func get_active_spawn_table() -> Array:
	var active: Array = []
	for entry: SpawnEntry in spawn_table:
		if _all_flags_set(entry.required_flags):
			active.append(entry)
	return active


## Returns the first variant key from world_flag_variants whose flag is
## currently set in WorldFlags, or an empty StringName if none match.
## A stage with more than one simultaneously-true variant flag should list
## world_flag_variants in priority order and this returns the first match.
func get_active_variant() -> StringName:
	for flag_name in world_flag_variants.keys():
		if WorldFlags.has_flag(flag_name):
			return world_flag_variants[flag_name]
	return &""


## Internal helper: true only if every flag in required_flags is currently
## set in WorldFlags (an empty array is vacuously true — no gating).
func _all_flags_set(required_flags: Array[StringName]) -> bool:
	for flag_name in required_flags:
		if not WorldFlags.has_flag(flag_name):
			return false
	return true
