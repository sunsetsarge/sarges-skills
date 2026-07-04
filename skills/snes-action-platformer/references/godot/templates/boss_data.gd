## BossData — data-driven boss definition.
##
## Attach: not attached to a node. This is a custom Resource class.
## Usage: New Resource > "BossData" in the Inspector, fill in fields, save
## as e.g. "boss_flame_mammoth.tres". A boss encounter scene reads this
## resource for HP, phases, intro sequencing, and weakness/stagger config
## rather than hardcoding those values per boss scene/script.
##
## Nested phase and attack-table rows live in their own Resource classes
## (boss_phase_data.gd, boss_attack_entry.gd) since Godot 4 only allows one
## class_name declaration per script file.
##
## Confirm class/property names against your installed Godot 4.x version.
class_name BossData
extends Resource

## Player-facing name, e.g. shown in the intro name-splash and pause menu
## boss-defeated log.
@export var display_name: String = ""

## Boss max HP.
@export var hp: int = 200

## Ordered list of phases. See boss_phase_data.gd — each phase has an HP%
## threshold and its own attack_table. A boss AI script should evaluate
## phases in descending threshold order and use the first whose threshold
## is >= the boss's current HP fraction.
@export var phases: Array[BossPhaseData] = []

## Intro sequence configuration: walk-in distance/speed, pose animation
## name, and name-splash text/duration. Kept as a Dictionary rather than a
## dedicated nested Resource class since intro sequencing tends to be
## boss-specific and doesn't benefit as much from strict per-field typing —
## a project doing many bosses with an identical intro shape may want to
## promote this to its own IntroConfig Resource class later, following the
## same pattern as boss_phase_data.gd.
## Expected keys (all optional, boss AI script decides defaults for
## missing keys):
##   "walkin_distance_px": float  — how far the boss walks in before combat starts
##   "walkin_speed_px_s": float   — walk-in movement speed
##   "pose_animation": StringName — animation name played during walk-in
##   "name_splash_text": String   — text shown in the name-splash UI
##   "name_splash_duration": float — seconds the name-splash stays on screen
@export var intro_config: Dictionary = {
	"walkin_distance_px": 96.0,
	"walkin_speed_px_s": 40.0,
	"pose_animation": &"walk",
	"name_splash_text": "",
	"name_splash_duration": 2.0,
}

## StringName id matched against an incoming projectile/attack's weapon_id
## (see WeaponData.weakness_target and combat.md's weapon-system flow) to
## apply bonus damage. E.g. a "boss_flame" BossData sets this to
## &"boss_flame" and an ice-type WeaponData sets its weakness_target to the
## same value.
@export var weakness_weapon_id: StringName = &""

## HP-chunk or hit-count threshold that triggers a stagger/vulnerable
## window, plus how long that window lasts. Kept as a small Dictionary
## rather than a dedicated class since it's just two related numbers.
## Expected keys:
##   "hits_to_stagger": int   — consecutive hits (within a short window,
##                              typically reset if the boss goes too long
##                              without being hit) required to trigger a
##                              stagger
##   "stagger_duration": float — seconds the boss stays staggered/open to
##                                bonus damage before resuming its attack
##                                pattern
@export var stagger_config: Dictionary = {
	"hits_to_stagger": 5,
	"stagger_duration": 1.5,
}
