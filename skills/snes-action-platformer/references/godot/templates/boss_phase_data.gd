## BossPhaseData — one phase in a BossData.phases array.
##
## Attach: not attached to a node. This is a custom Resource class, used as
## the element type of BossData.phases (see boss_data.gd). Kept as its own
## class so each phase gets a typed threshold and its own attack table.
##
## Confirm class/property names against your installed Godot 4.x version.
class_name BossPhaseData
extends Resource

## HP percentage (0.0-1.0) at or below which this phase becomes active.
## E.g. 1.0 for the opening phase, 0.5 for a "phase 2 kicks in at half
## health" transition, 0.2 for a final-phase enrage. A boss AI script
## should check phases in descending threshold order and use the first
## one whose threshold >= current HP fraction.
@export var threshold: float = 1.0

## This phase's available attacks. See boss_attack_entry.gd — each entry
## has a weight (for weighted-random selection), a cooldown, and an
## optional precondition hook.
@export var attack_table: Array[BossAttackEntry] = []
