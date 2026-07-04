## BossAttackEntry — one entry in a BossPhaseData.attack_table.
##
## Attach: not attached to a node. This is a custom Resource class, used as
## the element type of BossPhaseData.attack_table (see boss_phase_data.gd
## and boss_data.gd). Kept as its own class for typed, Inspector-editable
## rows rather than a loosely-typed Dictionary.
##
## Confirm class/property names against your installed Godot 4.x version.
class_name BossAttackEntry
extends Resource

## Hook key an EnemyAI / boss behavior script switches on to run this
## attack's actual logic. Not implemented here — this Resource only
## describes selection weighting and timing, not behavior.
@export var id: StringName = &"attack_lunge"

## Relative weight for weighted-random attack selection within this
## phase's attack_table. Higher weight = picked more often. Weights don't
## need to sum to any particular total — a boss AI script sums all
## eligible entries' weights and rolls against that sum.
@export var weight: int = 1

## Minimum seconds before this specific attack can be selected again after
## last being used.
@export var cooldown: float = 2.0

## Hook key checked by the boss AI before this attack is eligible for
## selection this cycle, e.g. &"player_grounded" (only usable while the
## player is on the ground) or &"player_airborne". Not implemented here —
## the boss AI script owns the actual precondition-check logic; this field
## just names which check to run. Leave as &"" for no precondition.
@export var precondition: StringName = &""
