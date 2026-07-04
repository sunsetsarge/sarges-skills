# Level Design

## Stage structure overview

- **Intro stage**: linear, death-proof (or near-death-proof — very generous checkpointing and low hazard damage), teaches every base verb in sequence, ends in a scripted easy miniboss and a story hook. Not selectable alongside the main 8; always played first.
- **8 selectable stages**: Maverick-style — player picks any order from a select screen, each themed around one boss archetype and one core environmental gimmick (see table below).
- Target **stage length: 3-5 minutes** of critical-path playtime for a skilled player (first-time players will run longer while learning the gimmick) — long enough to explore a full gimmick and a mid-boss, short enough that a death doesn't cost more than a couple of minutes of replay.
- **Difficulty curve within a stage**: introduce the gimmick in a low-stakes area first (no fall hazard, no enemies, or very forgiving ones), then combine it with basic enemies, then combine it with platforming challenge, then finally combine gimmick + enemies + platforming together right before the boss door. This "verb, then verb+challenge, then verb+challenge+stakes" ramp is the same teaching pattern the intro stage uses for the whole game, just compressed to one gimmick.
- **Checkpoint before gimmick escalation, and checkpoint before the boss door.** A death should never cost the player a full re-learn of the gimmick's introduction, and should never force a full gimmick gauntlet replay just to re-attempt a boss.

## The 8 stage gimmicks

Each row names a concrete parameter or two to start from — treat these as `game-feel.md`-style tuned starting points, not exact requirements.

| Theme | Gimmick | Concrete parameters |
|---|---|---|
| Ice / Frost | Slippery ground physics | On ice tiles, replace normal near-instant deceleration (see `game-feel.md`) with a much longer decel window — 15-25 ticks to stop from walk speed instead of 1-3. Keep acceleration itself relatively fast so turning isn't *impossible*, just imprecise. Jump arcs are unaffected (gravity/jump velocity stay the same) — only ground friction changes, which keeps the gimmick legible as "the floor is the problem," not "physics broke." |
| Volcanic / Flame | Lava hazards + conveyors | Lava = instant-death or heavy fixed damage on contact (pick one convention project-wide). Conveyor tiles apply a constant extra horizontal velocity (e.g. +/-60 px/s) on top of player input while standing on them — input should still be able to fight and overcome a conveyor moving toward a hazard, or the conveyor becomes an unfair instant-death strip rather than a platforming puzzle. |
| Storm / Airship | Wind gusts | Periodic (e.g., every 3-5 s) directional wind pulses lasting ~1-2 s, applying a continuous force to horizontal (and optionally vertical, for updrafts) velocity independent of player input. Telegraph gust timing visually (particle streaks, flags, a wind-up sound) 0.5-1 s before it starts so it reads as reactable, not random. |
| Electric / Darkness | Reduced light radius | Camera/render shows only a limited-radius circle or cone around the player (e.g., 3-4 tile radius); everything outside it is black or near-black. Combine with periodic lightning-flash beats that fully reveal the screen for a few frames every several seconds, giving the player brief "memorize the room" windows — this keeps the gimmick about attention and memory rather than pure blind guessing. |
| Camouflage | Stealth/spike gauntlet | Enemies or hazards that are visually camouflaged into the background until triggered (proximity or a tell like a shadow/glint) — always give *some* tell (a subtle outline shimmer, a shadow cast on the floor) so a first-time death teaches the trick rather than feeling like an unavoidable gotcha. Spike sections pair with this as instant-hazard obstacles requiring the player to have learned to look for the camouflage tell first. |
| Mine-cart | Auto-scroll ride segment | See Auto-scroll rules below — this is the genre's classic forced-scroll gimmick stage, built around dodging obstacles and enemies while horizontal (or track-following) movement is not fully player-controlled. |
| Water / Aquatic | Buoyancy + altered jump | Reduce effective gravity substantially underwater (e.g., to 30-40% of the normal `game-feel.md` value) and correspondingly reduce jump velocity magnitude so jump arcs stay proportional rather than becoming absurdly floaty. Add a slow natural upward drift (small negative constant added to vertical velocity) to simulate buoyancy, and cap both rise and fall speeds tighter than the normal terminal velocity so the whole stage reads as "underwater," not "low gravity moon stage." |
| Teleport maze | Non-linear teleporter network | A set of teleporter pads connecting non-adjacent rooms, where the *same visual room* can be reached via different pads that each lead somewhere different, or where pads cycle destinations on a timer/counter. Always give the player a landmark or map ping showing which pad they just used and general direction/floor of the destination — full disorientation with zero information reads as a design flaw, not challenge, in a genre otherwise built on tight player feedback. |

## Cross-stage environmental state: WorldFlags

Defeating a stage's boss can permanently alter *other* stages, in addition to granting a weapon — this is the substitute for full Metroidvania map interconnection, giving backtracking value without requiring every stage to physically connect into one map.

**Pattern**: a single global `WorldFlags` data store (a flat set of boolean/enum flags, e.g. `flame_boss_defeated: true`) that every stage reads at load time to decide which variant of its hazards/geometry to spawn. Stages never write to each other directly — they only read WorldFlags, and only that stage's own boss-defeat event writes the flag. This keeps the dependency direction one-way and easy to reason about (no stage needs to know about another stage's internals, only about a shared flag name).

Concrete examples:

- **Flame boss defeated -> Frost stage**: lava/magma hazard tiles in the Frost stage that were previously deadly are re-flagged as cooled solid platforms once `flame_boss_defeated` is true — opening a shortcut or a hidden-path route that was previously blocked by hazard tiles occupying that space.
- **Storm boss defeated -> Airship-adjacent stage**: wind-gust hazard pulses (see gimmick table above) stop firing entirely in any stage that shares the "airship" environmental family once `storm_boss_defeated` is true, since the in-fiction justification is that the storm generating the gusts has been stopped at its source.
- **Volt boss defeated -> Electric/Darkness stage**: the reduced-light-radius gimmick is lifted (full visibility restored) once `volt_boss_defeated` is true, in-fiction because the boss was powering the blackout, mechanically making a previously memory-heavy stage fully readable on a return visit.

Data hook: implement `WorldFlags` as a simple key-value store that is part of the save schema (see `architecture.md`), loaded once at game start and checked by each stage's load routine before it spawns its hazard/geometry variants — never re-checked mid-stage, to avoid a live hazard flickering state under the player's feet if a flag were somehow toggled mid-play.

## Checkpoints

- **Placement rule**: before every gimmick escalation step and always immediately before a boss door (see Stage Structure above). Additionally place one after any lengthy no-checkpoint gauntlet exceeds roughly 45-60 seconds of replay cost, even mid-gimmick, so a single mistake never costs more than about a minute.
- **Death behavior**: on death, respawn at the last checkpoint with full HP restored (sub-tanks are NOT auto-consumed on death — that would defeat their purpose as a player-chosen resource) and with the ammo/ammo ability inventory as it stood at checkpoint save time, not as it stood at moment of death (this avoids punishing experimentation with special-weapon ammo right before a death).
- **What persists across death**: collected heart tanks, armor upgrades, and WorldFlags always persist (they are permanent unlocks, not stage-run state). Enemies defeated since the last checkpoint reset (respawn) on death/reload from checkpoint — this is standard and expected in the genre, unlike a full save/reload which may or may not reset them per project convention.

## Mid-bosses

- Placed roughly at the stage's midpoint, functioning as the gate between "gimmick introduction" and "gimmick + full challenge" halves of the stage.
- **Arena lock**: entering the mid-boss room triggers a door/shutter closing behind the player (see `boss-design.md` for the shared ritual), preventing retreat until the fight resolves.
- **Reward**: typically a health/ammo refill drop, sometimes a small permanent pickup (ammo tank expansion), but never a heart tank or armor piece — those are reserved for full boss fights and hidden-path exploration, keeping mid-bosses feeling like a real but lesser obstacle.

## Ride armor (pilotable mech)

An optional pilotable vehicle segment, usually introduced in one specific stage per project (not all 8).

- **Stats**: typically has its own separate HP pool (often larger and separately tracked from the player's own HP), a heavy melee or ranged attack distinct from the buster, and altered movement (often no jump, or a lower single hop, trading platforming agility for raw offense/defense).
- **Entry/exit**: the player mounts by walking into the ride armor's location; exit is a manual player-initiated button press that drops the player back to on-foot at the ride armor's current position, generally with a brief invulnerability window on dismount since the player is momentarily exposed. Exiting instantly ends the ride-armor state and re-enables all base moveset states.
- **Required vs optional**: design intent should be decided explicitly per stage — a ride-armor segment that's *required* to cross a hazard the base moveset genuinely cannot cross is fine as a set-piece, but if the ride armor is meant purely as an optional power fantasy (a stronger way to clear an otherwise-normal section), make sure the on-foot route is still fully completable so skilled/upgraded players aren't forced into it.

## Auto-scroll segments

Forced-scroll sections (the mine-cart gimmick above is the canonical example, but auto-scroll can appear standalone) trade player pacing control for tension. Keep them fair:

- **Never require a reaction faster than the telegraph allows** — every hazard in an auto-scroll section must be visible on screen (or clearly telegraphed just off the leading edge of the camera) for enough time, at the current scroll speed, for a player to react. As a starting rule of thumb, a hazard should be visible for at least 0.75-1 s before it becomes reachable by the scroll.
- **Scroll speed should not exceed the player's ability to out-position it** — the point is constant forward pressure, not a race the player can't win; player horizontal movement speed should generally exceed scroll speed so falling behind is recoverable, not an instant death sentence, unless "don't fall behind the screen edge" is the explicit intended hazard (in which case telegraph the screen-edge kill clearly).
- **No blind drops**: never place a hazard immediately below/ahead of a point the player cannot see until they are already committed to falling/moving into it — auto-scroll removes the player's ability to simply wait and look, so the level must compensate by giving full sightlines instead.
- Checkpoint immediately before and, if the segment is long (>30-45s), at reasonable intervals within an auto-scroll gauntlet, since a single mistimed jump shouldn't force a full replay of an already-linear, low-agency section.

## Boss-arena camera lock and door/shutter ritual

Shared with `boss-design.md`'s ritual intro sequence — noted here for the level-design side of the contract: the room geometry itself must support a hard camera lock (no scrolling once the shutter closes) and the shutter/door object must be a real collidable piece of level geometry that seals the only exit, not just a visual dressing element. See `boss-design.md` for the full intro sequence beat-by-beat.
