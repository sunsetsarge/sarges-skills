## DropEntry — one row in an EnemyData drop table.
##
## Attach: not attached to a node. This is a custom Resource class, used as
## the element type of EnemyData.drop_table (see enemy_data.gd). Kept as
## its own small resource class (rather than a flat Dictionary) so each
## entry gets typed, Inspector-editable fields when shown as an array
## element in the Inspector.
##
## Confirm class/property names against your installed Godot 4.x version.
class_name DropEntry
extends Resource

## What this entry drops. Match these strings against whatever pickup/item
## system reads them (e.g. a PickupSpawner keyed by drop_id). Common
## values: &"health_small", &"health_large", &"ammo", &"rare_drop".
@export var drop_id: StringName = &"health_small"

## Chance (0.0-1.0) this entry triggers when the drop table rolls. Multiple
## entries are independent rolls, not a normalized distribution — this
## keeps the table simple to reason about and easy to add entries to
## without rebalancing every other entry's probability. A drop-roller
## script should loop every DropEntry in the table and roll each
## independently against randf() < entry.chance.
@export var chance: float = 0.1
