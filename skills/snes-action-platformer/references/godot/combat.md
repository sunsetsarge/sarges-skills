# Combat System (Godot 4.3+)

Hitbox/Hurtbox pattern, i-frames, contact damage, projectile pooling, and the full weapon-fire flow. See `templates/hitbox.gd`, `templates/hurtbox.gd`, `templates/projectile.gd`, `templates/projectile_pool.gd` for the implementing scripts.

## Table of Contents

- [Hitbox/Hurtbox Pattern](#hitboxhurtbox-pattern)
- [I-Frames](#i-frames)
- [Contact Damage](#contact-damage)
- [Projectile Pooling](#projectile-pooling)
- [Weapon System Flow](#weapon-system-flow)

## Hitbox/Hurtbox Pattern

Two distinct `Area2D`-based component types, kept deliberately separate rather than one combined "damage area" node, because a single actor frequently needs several of one and none of the other at different times (a boss has multiple Hitboxes for different attacks but one Hurtbox; a projectile has a Hitbox but no Hurtbox at all):

- **Hitbox** — *deals* damage. Lives on the `player_attack` layer (3) for anything the player's attacks touch enemies with, or `enemy_attack` (5) for anything enemies deal damage to the player with. Cross-reference `project-setup.md`'s collision layer/mask table: a player Hitbox has mask = `enemy` (4), an enemy Hitbox has mask = `player` (2) — a Hitbox's mask is what it's watching for, i.e. the opposing team's Hurtbox layer.
- **Hurtbox** — *receives* damage. Lives on `player` (2) for the player, `enemy` (4) for enemy characters. A Hurtbox's mask is set to watch for the opposing team's Hitbox/attack layer (player Hurtbox mask includes `enemy_attack`, enemy Hurtbox mask includes `player_attack`).

This split means a single enemy can have one Hurtbox (its body, receiving damage) plus three different Hitboxes active at different points in its attack animations (a melee swing hitbox, a projectile-spawn point, a contact-damage body hitbox) without any of them needing to know about each other — each Hitbox independently finds and calls into whatever Hurtbox it overlaps.

## I-Frames

After a Hurtbox's `take_damage()` runs (see `player-controller.md`'s Hurt/I-Frame Flow for the player-side state consequences), the Hurtbox itself:

1. Sets an internal `is_invulnerable: bool = true` flag and starts a `Timer` (or manually counts down a float) for `iframe_duration` (1.0s per the canonical tunable).
2. **Sets `monitoring = false` on itself** for that same duration.

The `monitoring = false` step is the actual mechanism that matters, not just a defensive flag check — Area2D's `monitoring` property controls whether it detects overlaps *at all*. Turning it off means the physics engine stops reporting `area_entered`/`body_entered` signals for this Hurtbox entirely during i-frames, which is what prevents a *contact-damage* enemy (see below) from re-triggering every physics tick it remains overlapped with the player (a stationary contact-damage enemy standing in the same spot as the player after a hit would otherwise fire `take_damage` 60 times a second — the flag alone doesn't stop the overlap signal from firing, only whether you *act* on it, so `monitoring = false` is the layer that actually needs to change). A flag-only check (`if is_invulnerable: return` inside `take_damage`) is a reasonable *second* layer of defense for damage sources that call `take_damage()` directly rather than via overlap signals, but `monitoring = false` is what's doing the real work against contact damage specifically.

Re-enable `monitoring = true` and clear `is_invulnerable` when the timer fires.

## Contact Damage

For simple touch-damage enemies (a walking enemy that just hurts on contact, no separate attack animation/hitbox needed), skip the full Hitbox setup — instead, the enemy's own body-adjacent `Area2D` (on `enemy_attack` layer, or the same node reused with both `enemy` and `enemy_attack` layers if you want to simplify further) directly deals `contact_damage` (a field read straight off that enemy's `EnemyData` resource) on overlapping the player's Hurtbox. This is a deliberate simplification vs. a full Hitbox for the common case of "this enemy just needs to hurt you by existing near you" — reserve a dedicated Hitbox node for enemies with distinct, separately-timed attacks (a lunge, a projectile spawn point, a delayed slam) where the "attack" is not simply "this enemy's whole body, always."

## Projectile Pooling

**Why**: instantiating a new `Node2D`-derived scene at runtime (`PackedScene.instantiate()`) and later freeing it (`queue_free()`) both cost real time — scene tree insertion/removal, `_ready()` callbacks, signal (re)connections, and eventual garbage collection of the freed instance. For a slow, occasional projectile this is invisible. For a rapid-fire weapon firing multiple shots per second, repeated instantiate/free cycles cause measurable per-frame hitches and GC churn, which is exactly the kind of stutter that breaks "movement feels right" for a fast-paced action game.

**Pattern**: preallocate a fixed number of instances of a given projectile scene once, up front (in `_ready()`), and recycle them for the rest of the game session — see `templates/projectile_pool.gd` for the implementation. `acquire()` hands out an inactive instance and marks it active; `release()` deactivates an instance and returns it to the available pool. **`instantiate()` and `queue_free()` are never called during actual gameplay** — only during initial pool setup (and, per the template's documented fallback, only if the pool needs to grow because it was exhausted).

## Weapon System Flow

Step by step, from input to final damage application — cross-references `data-resources.md` (WeaponData) and `player-controller.md` (the parallel charge/shoot action layer):

1. **Input**: shoot action pressed (tap) or released after a hold (charged tiers) — read by the player controller's parallel action layer, which has already been tracking `charge_time` against `charge_tier_2_time`/`charge_tier_3_time`.
2. **Read equipped WeaponData**: the currently-equipped `WeaponData` resource (from GameState's weapon-list) supplies `damage_tap`/`damage_charged_2`/`damage_charged_3`, `fire_cooldown`, `ammo_cost`, `projectile_scene`, `max_on_screen`.
3. **Check ammo and cooldown**: verify GameState's current ammo for this weapon id >= `ammo_cost`, and that enough time has passed since the last shot (a per-weapon cooldown timer >= `fire_cooldown`). If either check fails, the shot is silently refused (optionally play a dry-fire click SFX) — no pool interaction happens at all.
4. **Check on-screen cap**: before acquiring, verify the count of currently-active projectiles for this weapon is below `max_on_screen` (3, per the canonical tunable) — this is a separate counter from pool size (see `templates/projectile_pool.gd`'s header comment on that distinction). If at cap, refuse the shot the same as a failed cooldown check.
5. **Acquire from pool**: call `ProjectilePool.acquire()` (using the pool instance associated with `projectile_scene`) to get a free, currently-inactive projectile instance.
6. **Configure the acquired projectile**: set its `velocity` (direction from player facing + `speed` field), `damage` (whichever tier fired), `team` (Player), and `weapon_id` (so a later Hurtbox weakness check knows which weapon this was), then activate it (make visible, enable its Hitbox's `monitoring`).
7. **Flight**: the projectile moves under its own `_physics_process` (see `templates/projectile.gd`) until it hits something, exceeds `lifetime`, or leaves the visible screen area.
8. **On hit**: the projectile's Hitbox overlaps a target's Hurtbox and calls that Hurtbox's `take_damage(amount, knockback_dir, weapon_id)`.
9. **Weakness check**: inside `take_damage` (or in whatever boss-specific script wraps it), compare the incoming `weapon_id` against the target's `weakness_weapon_id` field (on `BossData`, or an equivalent field on `EnemyData` for regular enemies) — if they match, multiply damage by a weakness bonus (a reasonable starting multiplier is 2x-3x; tune per-boss, this is a design lever not a fixed constant).
10. **Apply damage, knockback, i-frames**: the Hurtbox applies the (possibly weakness-boosted) damage to the target's HP, computes knockback away from the projectile's `source_position`, and starts the target's i-frame window — same sequence described above in I-Frames, symmetric whether the target is the player or an enemy.
11. **Cleanup**: the projectile calls `release()` back to its `ProjectilePool` on hit (step 8 triggers this), on `lifetime` expiry, or on leaving the screen — never `queue_free()`.
