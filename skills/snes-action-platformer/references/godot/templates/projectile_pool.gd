## projectile_pool.gd — simple object pool for pooled projectiles.
##
## Attach to: a Node (e.g. a "ProjectilePool" node under an autoload, or
## one per weapon type if different weapons need different pool sizes/
## scenes). Set projectile_scene to a PackedScene whose root has
## projectile.gd attached (see projectile.gd).
##
## IMPORTANT — pool_size vs max_on_screen are DIFFERENT knobs:
##   - pool_size (this script): how many projectile Node instances exist
##     in memory at all, preallocated once at _ready(). This should
##     default at or above the max simultaneous on-screen cap so the pool
##     is never the bottleneck — template default 8, comfortably above the
##     canonical max_on_screen of 3.
##   - max_on_screen (WeaponData.max_on_screen, see weapon_data.gd): how
##     many of THIS WEAPON's projectiles are allowed to be ACTIVE
##     (acquired-and-not-yet-released) at once. This is a gameplay/balance
##     cap enforced by the WeaponSystem/firing code BEFORE it ever calls
##     acquire() — see references/godot/combat.md's weapon-system flow,
##     step 4. This script does not know about or enforce max_on_screen —
##     that check happens one layer up, in the code that decides whether
##     to fire at all.
##
## instantiate() and queue_free() are called ONLY in _ready() (initial
## preallocation) and _grow_pool() (the documented exhaustion fallback) —
## never during normal gameplay firing/hit/release cycles.
##
## Confirm class/property names against your installed Godot 4.x version.
extends Node

@export var projectile_scene: PackedScene

## How many instances to preallocate. Keep this at or above the largest
## max_on_screen value across all weapons that share this pool, with some
## headroom — 8 is a reasonable default for a max_on_screen of 3.
@export var pool_size: int = 8

## What to do when acquire() is called with no free instance available:
## true = grow the pool by instantiating one more (logs a warning, since
## repeated growth means pool_size was set too low and should be raised);
## false = refuse to fire, acquire() returns null and the caller must
## handle that (typically: just don't fire this frame).
@export var grow_on_exhaustion: bool = true

var _pool: Array[Node] = []
var _in_use: Array[Node] = []


func _ready() -> void:
	assert(projectile_scene != null, "ProjectilePool.projectile_scene must be assigned")
	for i in range(pool_size):
		_pool.append(_instantiate_one())


func _instantiate_one() -> Node:
	var instance: Node = projectile_scene.instantiate()
	add_child(instance)
	if instance.has_method("_ready"):
		pass  # _ready() already ran via add_child(); projectile.gd's _ready() sets it inactive/invisible.
	if "owning_pool" in instance:
		instance.owning_pool = self
	return instance


## Returns a free, inactive instance, or null if the pool is exhausted and
## grow_on_exhaustion is false. Caller is responsible for calling
## activate()/configuring the returned instance — this method only hands
## out a raw node, it does not position or fire it.
func acquire() -> Node:
	if _pool.is_empty():
		if grow_on_exhaustion:
			push_warning("ProjectilePool for %s exhausted at pool_size=%d — growing by 1. Consider raising pool_size." % [projectile_scene.resource_path, pool_size])
			_pool.append(_instantiate_one())
			pool_size += 1
		else:
			return null

	var instance: Node = _pool.pop_back()
	_in_use.append(instance)
	return instance


## Deactivates an instance and returns it to the available pool. Safe to
## call even if the instance isn't currently tracked as in-use (a no-op in
## that case) so projectile.gd's _release() can call this unconditionally.
func release(instance: Node) -> void:
	var idx: int = _in_use.find(instance)
	if idx != -1:
		_in_use.remove_at(idx)
	if not _pool.has(instance):
		_pool.append(instance)
