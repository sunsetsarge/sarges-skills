## WeaponData — data-driven weapon definition.
##
## Attach: not attached to a node. This is a custom Resource class.
## Usage: right-click in the FileSystem dock > New Resource > "WeaponData" >
## fill in fields in the Inspector > save as e.g. "weapon_buster.tres".
## Reference the saved .tres from GameState's equipped-weapon list, or any
## @export var weapon: WeaponData field. See references/godot/data-resources.md
## for the full worked example of adding a new weapon with zero code changes.
##
## Confirm class/property names against your installed Godot 4.x version.
class_name WeaponData
extends Resource

## Stable identifier used for equality checks (e.g. matching against
## BossData.weakness_weapon_id). Never display this to the player directly;
## use display_name for UI.
@export var id: StringName = &""

## Player-facing name shown in weapon-select UI / HUD.
@export var display_name: String = ""

## Damage dealt by an uncharged (tap) shot.
@export var damage_tap: int = 1

## Damage dealt by a tier-2 charged shot (held for charge_tier_2_time, see
## player_controller.gd — canonical default 0.55s).
@export var damage_charged_2: int = 3

## Damage dealt by a tier-3 / full-charge shot (held for charge_tier_3_time,
## canonical default 1.1s).
@export var damage_charged_3: int = 6

## Maximum ammo this weapon can carry. Buster-type weapons with infinite
## ammo can set this to -1; WeaponSystem code should treat ammo_max < 0 as
## "unlimited" and skip ammo deduction entirely.
@export var ammo_max: int = 28

## Ammo consumed per shot fired (tap shot; charged tiers may cost more —
## a project wanting per-tier ammo cost can add ammo_cost_charged_2/3
## fields following the same pattern as the damage tiers above).
@export var ammo_cost: int = 1

## Scene instantiated (via a ProjectilePool, never directly) when this
## weapon fires. Must have projectile.gd attached to its root Area2D and a
## Hitbox child — see templates/projectile.gd and templates/hitbox.gd.
@export var projectile_scene: PackedScene

## Minimum seconds between shots. Enforced by whatever WeaponSystem script
## reads this resource — see references/godot/combat.md's weapon flow.
@export var fire_cooldown: float = 0.2

## Maximum number of this weapon's projectiles allowed active on screen at
## once (canonical default: 3). This is a *gameplay* cap enforced by the
## firing code before it ever calls ProjectilePool.acquire() — it is a
## different number from ProjectilePool.pool_size (how many instances
## exist in memory). See templates/projectile_pool.gd's header comment.
@export var max_on_screen: int = 3

## Movement-speed multiplier applied to the player while this weapon is
## equipped/actively firing (1.0 = no change). This is a hook other systems
## (player_controller.gd's speed calculations) can read — e.g. a heavy
## charge weapon that slows the player while charging, or a mobility
## weapon that speeds them up. Most weapons should leave this at 1.0.
@export var move_speed_multiplier: float = 1.0

## StringName id of the boss (matching a BossData.weakness_weapon_id) this
## weapon deals bonus damage against. Leave empty (&"") if this weapon has
## no specific boss weakness target.
@export var weakness_target: StringName = &""
