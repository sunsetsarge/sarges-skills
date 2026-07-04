# Data-Driven Content via Godot Resources

How weapons, enemies, stages, and bosses are defined as data — not hardcoded in scripts — using custom `Resource` classes. See `templates/weapon_data.gd`, `enemy_data.gd`, `stage_data.gd`, `boss_data.gd` for the actual class definitions this doc explains.

## Table of Contents

- [The Resource Pattern](#the-resource-pattern)
- [Why Resources Beat Raw JSON](#why-resources-beat-raw-json)
- [How Designers Create .tres Files](#how-designers-create-tres-files)
- [StageData <-> WorldFlags](#stagedata---worldflags)
- [Worked Example: New Weapon, Zero Code Changes](#worked-example-new-weapon-zero-code-changes)

## The Resource Pattern

A custom Resource is a plain GDScript file that declares `class_name` and `extends Resource`, then exposes fields via `@export`:

```gdscript
class_name WeaponData
extends Resource

@export var id: StringName = &""
@export var display_name: String = ""
@export var damage_tap: int = 1
```

Once this script exists, Godot's editor treats `WeaponData` as a first-class type: it shows up in the "New Resource" picker, any `@export var weapon: WeaponData` field on another node shows a proper typed resource-picker in the Inspector, and you can save individual instances of it to disk as `.tres` (text) or `.res` (binary) files — each `.tres` file is one "weapon," editable without touching code.

## Why Resources Beat Raw JSON

- **Inspector-editable.** A designer (even solo-dev you, three months later, having forgotten the JSON schema) fills in fields through Godot's Inspector UI — text fields, number spinners, resource pickers, dropdowns for enums — instead of hand-editing a text file and hoping the commas are right.
- **Type safety.** `@export var damage_tap: int` means the Inspector only accepts an integer there, and any script reading `weapon_data.damage_tap` gets autocomplete and compile-time type checking. A JSON field is just `"damage_tap": "1"` (maybe a string by typo) until something crashes at runtime trying to do math on it.
- **Sub-resources nest naturally.** A `StageData` resource can `@export var spawn_table: Array[SpawnEntry]` where `SpawnEntry` is itself another small custom Resource — the Inspector renders this as an expandable array of editable sub-objects. Representing the same nested structure in raw JSON means hand-writing nested objects/arrays with no schema validation until you write one yourself.
- **Load-through-cache, no manual parsing.** `.tres`/`.res` files are loaded via Godot's built-in resource system (`load("res://data/weapons/weapon_buster.tres")` or a `@export var weapon: WeaponData` field referencing it directly) — Godot handles caching (loading the same path twice returns the same in-memory instance rather than re-parsing), reference resolution for nested sub-resources, and versioned save/load compatibility. Raw JSON needs you to write and maintain a parser, a schema, and your own caching if you want to avoid re-reading the same file repeatedly.
- **`.tres` is version-control-friendly.** The text `.tres` format is human-readable and diffable in git — a designer changing one weapon's damage value produces a small, readable diff, similar to what you'd get from JSON, without giving up any of the above benefits. (Use `.tres`, not the binary `.res`, specifically so this stays true.)

## How Designers Create .tres Files

No code required per new item:

1. In the FileSystem dock, navigate to (or create) a folder like `res://data/weapons/`.
2. Right-click > **New Resource...**
3. In the type picker, search for the custom class name (e.g. `WeaponData`) and select it.
4. Godot creates a new unsaved resource and opens it in the Inspector — fill in every `@export` field (id, display_name, damage tiers, projectile scene reference, etc.) directly in the Inspector UI.
5. Save it (Ctrl+S or the save icon in the Inspector) as e.g. `weapon_buster.tres` in that folder.
6. Reference it wherever needed — drag the `.tres` file from the FileSystem dock onto any `@export var weapon: WeaponData` field on another node/resource, or load it by path in code.

That's the entire workflow for adding new data-driven content. No script is opened or edited.

## StageData <-> WorldFlags

A stage's spawn table and gimmick config can be conditioned on the save-independent world state tracked by the `WorldFlags` autoload (see `project-setup.md`'s autoload table):

- **`world_flags_required: Array[StringName]`** on a spawn-table entry (or the whole `StageData`) — the WorldFlags autoload must have **all** of these flags set true before that entry/spawn becomes active. Example: a shortcut door in Stage 1 that only appears after `world_flags_required = ["boss_heat_defeated"]` is satisfied, because defeating the heat-themed boss is what conceptually "unlocks" that shortcut.
- **`world_flag_variants: Dictionary`** — maps a flag name (StringName key) to an alternate spawn/tile variant key (e.g. `{"boss_heat_defeated": "shortcut_open"}`). Stage load logic checks this dictionary against current WorldFlags state to decide which *variant* of a spawn or tile group to use, rather than a strict on/off gate — useful when revisiting an earlier stage should swap in a removed hazard, an opened shortcut, or a different enemy loadout rather than simply adding/removing one thing.

The flow: a boss's `StageData` (or the boss encounter script) calls `WorldFlags.set_flag("boss_heat_defeated", true)` on defeat. The *next time* any stage (including earlier ones) loads, its `StageData.get_active_spawn_table()` helper reads `WorldFlags` and filters/swaps entries accordingly — WorldFlags is the single source of truth both stages read, so Stage 1 doesn't need to know anything about Stage 4's boss beyond the flag name.

## Worked Example: New Weapon, Zero Code Changes

Goal: add a brand-new weapon, "Ice Shard," with zero script edits.

1. In the FileSystem dock, duplicate an existing weapon resource, e.g. `weapon_buster.tres` -> `weapon_ice_shard.tres` (Ctrl+D or right-click > Duplicate).
2. Open `weapon_ice_shard.tres` in the Inspector. Change:
   - `id` to `&"ice_shard"`
   - `display_name` to `"Ice Shard"`
   - `damage_tap` / `damage_charged_2` / `damage_charged_3` to whatever balance numbers fit (e.g. 2 / 4 / 8)
   - `projectile_scene` to a new `ice_shard_projectile.tscn` (a scene with `projectile.gd` + a `Hitbox` child, following the same shape as any other projectile scene)
   - `weakness_target` to the StringName id of whatever boss this weapon is strong against (e.g. `&"boss_flame"`)
3. Save the `.tres`.
4. Add the new `WeaponData` resource to the player's weapon-list array (an `Array[WeaponData]` field, likely on GameState or a `PlayerLoadout` resource) — drag the new `.tres` into an empty array slot in the Inspector, or append it via whatever menu the project uses to manage the player's weapon roster.
5. Done. No script edits anywhere.

This works because `WeaponSystem` code (see `combat.md`'s weapon-system flow) reads every field it needs — damage, cooldown, ammo cost, projectile scene, weakness target — off whichever `WeaponData` resource happens to be currently equipped. It never branches on `if weapon.id == "buster": ... elif weapon.id == "ice_shard": ...` — that kind of identity-switching is exactly what would force a code change per new weapon, and is the anti-pattern this data-driven approach exists to avoid.
