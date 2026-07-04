# Architecture

Engine-agnostic structural patterns for implementing the mechanics described in `game-feel.md`, `mechanics.md`, `level-design.md`, and `boss-design.md`. Everything here is described in terms of states, data structures, and rules — apply it to whatever engine is actually in use.

## Table of contents

1. [Player as a locomotion FSM](#player-as-a-locomotion-fsm)
2. [The parallel action layer (charging/shooting)](#the-parallel-action-layer-chargingshooting)
3. [Fixed-timestep AABB collision vs tilemap](#fixed-timestep-aabb-collision-vs-tilemap)
4. [Camera as a mode state machine](#camera-as-a-mode-state-machine)
5. [Data-driven content](#data-driven-content)
6. [Object pooling for projectiles and effects](#object-pooling-for-projectiles-and-effects)
7. [Hitboxes, hurtboxes, and team layers](#hitboxes-hurtboxes-and-team-layers)
8. [Save system](#save-system)
9. [Input abstraction](#input-abstraction)

## Player as a locomotion FSM

Model the player's *locomotion* (not combat) as a finite state machine with these states:

`Idle`, `Run`, `Jump`, `Fall`, `Dash`, `DashJump`, `WallSlide`, `WallJump`, `Hurt`, `Dead`

### Transition table

| From | Trigger | To |
|---|---|---|
| Idle | Directional input pressed (grounded) | Run |
| Idle | Jump pressed (grounded, or within jump buffer/coyote) | Jump |
| Idle | Dash pressed (grounded) | Dash |
| Idle | Grounded check fails (walked off ledge, floor removed) | Fall |
| Idle | Damaged | Hurt |
| Run | Directional input released, velocity reaches zero | Idle |
| Run | Jump pressed | Jump |
| Run | Dash pressed | Dash |
| Run | Grounded check fails | Fall |
| Run | Damaged | Hurt |
| Jump | Vertical velocity crosses zero and begins increasing (apex reached) | Fall |
| Jump | Dash pressed while airborne (if air dash available) | Dash (airborne variant) |
| Jump | Wall-cling condition met (into wall + falling — note: only after apex, see Fall) | — (see Fall's WallSlide transition; Jump itself does not slide) |
| Jump | Damaged | Hurt |
| Jump | Grounded check succeeds (rare — e.g., very short hop over a lip) | Idle or Run per held input |
| Fall | Wall-cling condition met (holding into adjacent wall while falling) | WallSlide |
| Fall | Grounded check succeeds | Idle or Run per held input |
| Fall | Dash pressed while airborne (if air dash available and unused this airborne period) | Dash (airborne variant) |
| Fall | Damaged | Hurt |
| Dash | Dash timer (0.35 s) expires, grounded | Idle or Run per held input |
| Dash | Dash timer expires, airborne | Fall (with velocity decay per `game-feel.md`'s dash-off-ledge rule) |
| Dash | Jump pressed during active dash | DashJump |
| Dash | Damaged | Hurt |
| DashJump | Vertical velocity crosses zero and begins increasing | Fall (retaining horizontal dash speed per `game-feel.md`) |
| DashJump | Wall-cling condition met | WallSlide |
| DashJump | Damaged | Hurt |
| WallSlide | Wall contact lost (player moves off wall, or reaches ground) | Fall or Idle/Run respectively |
| WallSlide | Jump pressed | WallJump |
| WallSlide | Damaged | Hurt |
| WallJump | Input-lock window (~0.1 s) expires, still airborne | Fall |
| WallJump | Wall-cling condition met again (chained wall-jump up a shaft) | WallSlide |
| WallJump | Grounded check succeeds | Idle or Run per held input |
| WallJump | Damaged | Hurt |
| Hurt | Control-lock duration (0.25 s) expires | Fall, Idle, or Run depending on grounded state at expiry |
| Hurt | HP reaches zero during Hurt | Dead |
| Any state | HP reaches zero | Dead |
| Dead | (terminal — respawn/reload transitions out of the FSM entirely, not a normal transition) | — |

Note: `Dash` covers both the ground-dash and air-dash cases — distinguish them with a sub-flag (`grounded: bool`) on entry rather than doubling the state count, since their exit rules differ (ground dash expiring transitions to Idle/Run, air dash expiring transitions to Fall) but their internal timer/cancel logic is otherwise identical.

## The parallel action layer (charging/shooting)

**Charging and shooting must be modeled as a separate, parallel state machine (or even simpler, a small independent flag/timer struct) running alongside the locomotion FSM above — never folded into the same states.**

Why this matters: the player can be in *any* locomotion state while charging or holding a charged shot (see `mechanics.md` — charge is explicitly orthogonal to locomotion). If charge state were instead encoded as additional locomotion states, the state count multiplies combinatorially: 10 locomotion states x 4 charge states (uncharged, charging-Lv1, charging-Lv2, charging-Lv3) = **40 states**, and every one of those 40 needs its own transition rules duplicated across all the charge variants. Any future addition (a new locomotion state, a new charge tier, a new weapon-equipped modifier) multiplies the count further. This is unmaintainable and is the single most common architecture mistake when implementing this genre.

Instead, keep two independent state holders:

- **Locomotion FSM** (above): owns position, velocity, grounded/walled flags, and the 10 named states.
- **Action layer**: owns current charge timer, current charge tier, equipped weapon, weapon ammo, and fire-input handling. It reads locomotion state only if needed for a specific rule (e.g., "cannot fire this specific weapon while wall-sliding," if such a rule exists for a given weapon) but does not itself have "combined" states — it is a flat data structure (charge tier, timer, equipped weapon ID) updated independently every tick, in its own step of the per-tick order (see `game-feel.md`'s input-reading order, step 8).

Any per-weapon exception to "orthogonal to everything" (e.g., a mobility weapon that *does* require a specific locomotion state to activate, such as a grapple only usable while airborne) should be expressed as a guard condition read *from* the action layer *into* the locomotion FSM's transition table, or vice versa — a one-directional check, not a merge of the two state machines into one.

## Fixed-timestep AABB collision vs tilemap

Run all collision resolution inside the fixed 60 Hz tick (see `game-feel.md`), never in a variable-rate render step, so results are deterministic and reproducible frame to frame.

- **Broadphase by tile lookup**: rather than testing the player's AABB against every tile in the level, compute the range of tile-grid cells the player's bounding box overlaps (or will overlap after this tick's movement) and only test collision against tiles within that small range. This keeps collision cost roughly constant regardless of level size.
- **Resolve X then Y (or Y then X, but pick one and apply it consistently)**: move and resolve horizontal position first, correcting for any horizontal wall penetration, then move and resolve vertical position second, correcting for any vertical floor/ceiling penetration. Resolving both axes in one combined step produces inconsistent corner-case behavior — e.g., approaching a tile corner diagonally can produce different results depending on approach angle if both axes are resolved simultaneously, whereas a fixed axis order gives a single, predictable, testable outcome (typically: horizontal resolution first is preferred since it keeps ground-following behavior on slopes/steps more forgiving before vertical is corrected).
- **One-way platforms**: these are solid from above only, and platform tiles should be flagged as such so the vertical-resolution pass ignores them entirely when the player's vertical velocity is upward (jumping into them from below), and treats them as solid only when the player's *previous* tick position was above the platform's top surface (falling/landing onto it), not merely "currently above it," to avoid snapping the player up onto a platform they're jumping past from the side.
  - **Drop-through input**: holding a distinct down+jump (or a dedicated drop button, per project convention) while standing on a one-way platform should briefly (a handful of ticks) disable one-way collision for that platform so the player falls through on purpose — implement this as a short timer/flag on the player rather than permanently removing the platform's collision, so it re-engages automatically.
- **Ladders**: treat a ladder tile as a distinct traversal mode that overrides normal gravity while the player is overlapping it and holding up/down input — grant a fixed vertical climb speed (separate tunable, not derived from walk/dash speed) and suppress normal gravity/jump physics while attached. Exiting a ladder (reaching its top/bottom, or pressing jump to launch off it) returns immediately to normal locomotion FSM state resolution.
- **Slopes are explicitly out of scope for a first pass** — flag them as a later addition. Sloped-tile collision (angled floor following, speed changes on slopes, slope-to-flat transitions) adds meaningfully more collision-resolution complexity (can't rely on simple axis-aligned tile membership; needs per-tile angle data and continuous position correction along the slope surface) for a genre where slopes are a relatively rare set-piece element rather than a core traversal surface. Build and ship the flat-tile collision model first; add slope support only if a specific stage design genuinely needs it.

## Camera as a mode state machine

Model the camera as its own small state machine, separate from both the player FSM and the action layer, with modes:

| Mode | Behavior |
|---|---|
| `DeadzoneFollow` | Default mode. The camera stays still while the player is within a central deadzone rectangle, and only scrolls (typically clamped to a max scroll speed) once the player nears the deadzone's edge — this avoids the camera nervously tracking every small player movement. |
| `LookAhead` | An extension of DeadzoneFollow that additionally biases the camera's target position in the player's current facing direction (and further in the dash direction while dashing), so the player can see further ahead when moving fast — this matters especially during dash and dash-jump, where seeing an upcoming hazard a beat earlier is the difference between a fair and unfair reaction window. |
| `RoomLock` | Triggered by entering a designated room-lock trigger volume; the camera snaps to and holds a fixed framing of the current room (no player-follow scrolling at all) until the player exits through a designated exit trigger. Used for tightly composed single-screen puzzle/combat rooms. |
| `BossArenaLock` | A specialized RoomLock variant entered via the ritual intro sequence (see `boss-design.md`) — camera is fixed to frame the boss arena, and does not release back to DeadzoneFollow/LookAhead until the boss is defeated (or the player dies/retreats, if retreat is permitted before the shutter fully seals). |
| `AutoScroll` | Camera moves under its own constant or scripted velocity, independent of player position (see `level-design.md`'s auto-scroll fairness rules) — player position is instead constrained to stay within the visible frame, often by a soft push-back force or a hard death-if-left-behind boundary, per project convention. |

Transitions between modes are driven by trigger volumes and scripted events (entering a boss arena, entering/exiting a room-lock zone, reaching an auto-scroll section's start/end marker) rather than by continuous position checks — this keeps camera-mode changes deliberate and level-designer-authored rather than emergent/accidental.

## Data-driven content

Weapons, enemies, bosses, and stages should be defined as **data files** (JSON, YAML, or equivalent structured format — the specific format is an engine/tooling choice, not a design requirement), not hardcoded in code, so content can be added, tuned, and balanced without a code change or recompile.

Suggested fields per content type (add project-specific fields as needed; this is a floor, not a ceiling):

**Weapon data**
- ID / display name
- Damage per hit (and per charge tier, if applicable)
- Ammo cost per use, max ammo pool size
- Projectile speed, lifetime, hitbox size
- Mobility-alteration flags (does this weapon create platforms / grant a dash / grapple, etc. — see `mechanics.md`)
- Weakness-chart relationships (what this weapon is strong against, per `mechanics.md`'s cycle)

**Enemy data**
- ID / display name
- Max HP, contact damage, knockback values
- Movement pattern reference (patrol, chase, stationary-turret, etc. — reference a shared behavior type rather than embedding unique code per enemy)
- Attack table (same shape as the boss attack table in `boss-design.md`, scaled down)
- Drop table (health/ammo/currency drop chances)

**Boss data**
- ID / display name, theme, weakness weapon ID, "beats" weapon ID (per the weakness cycle)
- Max HP, phase thresholds
- Full attack table (per `boss-design.md`'s schema: attack ID, weight, cooldown, positional precondition, phase availability, telegraph/active/recovery durations)
- Arena reference (which arena layout/room this boss uses)
- Weapon granted on defeat, WorldFlags written on defeat (see `level-design.md`)

**Stage data**
- ID / display name, theme, gimmick type reference (per `level-design.md`'s gimmick table)
- Tilemap/room reference
- Checkpoint positions
- Enemy/mid-boss/boss placement references (which enemy/boss data entries spawn where)
- WorldFlags read at load (which flags this stage checks, and what geometry/hazard variant each flag value maps to)
- Heart tank / sub-tank / armor-piece pickup placements, including hidden-path gating requirements (per `progression.md`)

## Object pooling for projectiles and effects

Pre-allocate a fixed pool of reusable projectile and particle-effect objects at level load, rather than allocating/freeing a new object on every shot fired or hit landed.

**Why**: at a locked 60 fps with potentially several weapons, multiple enemies, and hit-effect particles all firing simultaneously, per-object allocation (and garbage collection, in managed-memory engines) causes intermittent frame-time spikes — exactly the kind of hitch that breaks the frame-perfect timing this entire skill depends on (telegraph windows, coyote time, hit-stop). Pooling trades a small fixed upfront memory cost for eliminating that allocation spike class entirely.

Implementation shape: maintain a fixed-size array/list per object type (e.g., "player Lv1 shot pool," "enemy projectile pool," "hit-spark effect pool"), each sized to comfortably exceed the practical on-screen cap already established in `game-feel.md`/`snes-authenticity.md` (3 on-screen Lv1 shots, ~8-10 on-screen enemies/projectiles) with some headroom. On "spawn," pull an inactive entry from the pool and activate it; on expiry/despawn, deactivate it and return it to the pool rather than destroying it.

## Hitboxes, hurtboxes, and team layers

Separate the concept of "a shape that can deal damage" (hitbox) from "a shape that can receive damage" (hurtbox), and tag both with a **team layer** so collision-damage checks only compare across opposing teams:

| Layer | Applies to |
|---|---|
| `player-hurt` | The player's own damageable area. |
| `player-attack` | The player's buster shots, special weapons, melee hitboxes. |
| `enemy-hurt` | Enemy and boss damageable areas. |
| `enemy-attack` | Enemy and boss projectiles/melee hitboxes. |

A damage check only ever compares an `-attack` layer against the opposing team's `-hurt` layer (`player-attack` vs `enemy-hurt`, and `enemy-attack` vs `player-hurt`) — same-team pairs (`player-attack` vs `player-hurt`, or two enemies' attacks against each other) are never checked, which avoids needing special-case exclusion logic scattered through combat code.

**I-frames**: implement invincibility frames as a simple timer on the player (and optionally on enemies/bosses, for their own post-hit-stagger invulnerability if desired) that, while active, causes `player-hurt` layer checks to be skipped entirely — the hurtbox effectively doesn't exist for the duration, rather than existing but "taking zero damage," which keeps the check itself simple and also naturally prevents any secondary effects (knockback re-trigger, hit-stop re-trigger) from re-firing every tick during the invincibility window.

## Save system

Persist at minimum: bosses defeated, upgrades obtained, heart tank / sub-tank state, and WorldFlags. Example schema shape (field names illustrative, adapt to project conventions):

```
SaveData {
  bossesDefeated: [bossID, ...]            // which bosses are down (drives weapon unlocks + WorldFlags derivation)
  weaponsUnlocked: [weaponID, ...]
  armorUpgrades: { leg: bool, arm: bool, body: bool, head: bool }
  heartTanksCollected: [heartTankID, ...]   // or a simple count, if tanks are not individually tracked/re-visitable
  maxHP: int                                // derived from base HP + 2 per heart tank, but often cached directly
  subTanks: [ { capacity: int, currentFill: int }, ... ]   // 2-4 entries, per `progression.md`
  worldFlags: { flagName: bool, ... }        // flat key-value store, per `level-design.md`
  currentStage: stageID                      // or "stage-select," if between stages
  lastCheckpoint: { stageID, checkpointID }  // where to resume within a stage, if mid-stage save/quit is supported
}
```

Keep `worldFlags` as a genuinely flat structure (not nested per-stage) since stages only ever read it, never write to another stage's namespace — a flat global store keeps that one-way dependency simple to enforce (see `level-design.md`'s WorldFlags pattern).

## Input abstraction

Never read raw keyboard/controller codes directly in gameplay logic — define a layer of **virtual actions** (e.g., `MoveLeft`, `MoveRight`, `Jump`, `Dash`, `Fire`, `WeaponSwitchNext`, `WeaponSwitchPrev`, `DropThroughPlatform`) and have gameplay code query virtual-action state (pressed / held / released-this-tick), with a separate mapping layer translating physical inputs (specific keys, specific controller buttons/axes) onto those virtual actions.

Benefits this unlocks with effectively no extra cost if done from the start:

- **Buffering** (jump buffer, and any other buffered inputs a project wants) is implemented once, generically, against virtual actions — one buffering utility serves every buffered input rather than duplicating buffer-timer logic per physical key.
- **Remapping**: supporting user-customizable controls becomes a matter of editing the physical-to-virtual mapping table, with zero changes to gameplay code that only ever queries virtual actions.
- **Controller support** (and supporting multiple controller types/layouts) is purely a mapping-layer concern — gameplay code is entirely unaware of whether a `Jump` virtual action came from a keyboard key, a gamepad face button, or a D-pad-adjacent button on some third input device.

Read virtual-action state at a fixed point in the per-tick order (see `game-feel.md`'s input-reading order, step 1: buffer intake) so input handling is as deterministic as the physics it drives.
