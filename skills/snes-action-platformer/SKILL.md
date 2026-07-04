---
name: snes-action-platformer
description: >-
  Build SNES-era side-scrolling action-platformers in the Mega Man X mold —
  tight run-and-gun movement with dashing, wall-jumping, charge shots, special
  weapons with a boss-weakness chart, selectable Maverick-style stages,
  armor/heart/sub-tank upgrades, cross-stage environmental state, and
  multi-phase telegraphed bosses. Ships a tuned physics table (gravity, dash,
  coyote time, jump buffer — concrete starting numbers), an FSM player
  architecture, and copy-ready Godot 4 / GDScript templates with data-driven
  content via custom Resources; all design knowledge is engine-agnostic and
  layered so other engines can be added. USE THIS SKILL whenever the user
  wants to make, design, plan, or debug a 2D action platformer, run-and-gun,
  "Mega Man X style" or "Mega Man" style game, retro/SNES/16-bit platformer,
  metroidvania-lite action game, dash/wall-jump platformer, or boss-rush
  action game — even if they never name the genre precisely ("a game where
  you dash and shoot robots and pick stages in any order"). Also trigger for
  narrower asks inside the genre: tuning jump/dash/wall-jump feel or physics
  numbers, designing a boss weakness chart, adding a stage/boss/weapon to an
  existing game of this type, or fixing platformer feel bugs (floaty jump,
  jittery camera, eaten inputs). Output is always ORIGINAL IP — MMX is the
  analytical model, never the asset source.
metadata:
  version: 1.0.0
---

# SNES Action-Platformer Builder (Mega Man X mold)

Expert playbook for the 16-bit side-scrolling action-platformer: X-series
movement (dash, wall-kick, charge buster), 8 selectable gimmick stages, a
weakness-chart boss cycle, and metroidvania-lite upgrades — locked 60 fps at
256×224. This file is a **router**: read the sections you need, follow the
pointers, don't guess at numbers that are already written down.

## Layering rule (read this before extending the skill)

- `references/design/` is **engine-agnostic** genre knowledge. It never
  mentions GDScript or Godot nodes — pixels, seconds, and abstract data only.
- `references/godot/` is the **Godot 4.x implementation layer** that realizes
  the design layer.
- To target another engine (e.g. HTML5/canvas), add a sibling
  `references/html5/` implementation layer. **Do not touch the design layer
  to do it** — if you find engine-specific text in `design/`, that's a bug;
  move it down into the implementation layer.

## Original-IP guardrail

Mechanics are not copyrightable; assets and names are. Every game built with
this skill uses original characters, art, music, names, and story. Read
[references/design/authenticity-and-ip.md](references/design/authenticity-and-ip.md)
before shipping anything, and never put "Mega Man" in a title or store page.

## Reference map — when to read what

| You are... | Read |
|---|---|
| Tuning movement/physics, or feel is "off" | [design/game-feel.md](references/design/game-feel.md) — the tunables table + the dash/coyote/buffer interaction cluster |
| Implementing dash, wall-jump, charge shot, special weapons, weakness chart | [design/mechanics.md](references/design/mechanics.md) |
| Designing upgrades, heart/sub-tanks, hidden paths | [design/progression.md](references/design/progression.md) |
| Building the intro stage or the 8 stages, gimmicks, checkpoints, ride armor, cross-stage WorldFlags | [design/level-design.md](references/design/level-design.md) |
| Designing any boss (phases, telegraphs, intro ritual) | [design/boss-design.md](references/design/boss-design.md) |
| Resolution, palettes, parallax, sprite budgets, audio character | [design/snes-authenticity.md](references/design/snes-authenticity.md) |
| Structuring code: player FSM, collision, camera, pooling, save | [design/architecture.md](references/design/architecture.md) |
| Setting up the Godot project (pixel-perfect 60 fps config) | [godot/project-setup.md](references/godot/project-setup.md) — includes the quickstart |
| Writing/adapting the player controller | [godot/player-controller.md](references/godot/player-controller.md) + [templates/player_controller.gd](references/godot/templates/player_controller.gd) |
| Defining weapons/enemies/stages/bosses as data | [godot/data-resources.md](references/godot/data-resources.md) + the four `*_data.gd` templates |
| Camera behavior | [godot/camera.md](references/godot/camera.md) + [templates/camera_controller.gd](references/godot/templates/camera_controller.gd) |
| Damage, hurtbox/hitbox, projectiles, weapon flow | [godot/combat.md](references/godot/combat.md) + `projectile*.gd`, `hurtbox.gd`, `hitbox.gd` templates |
| Speccing sprites or audio for an artist/musician (or AI gen) | [assets/spritesheet-spec.md](assets/spritesheet-spec.md), [assets/audio-spec.md](assets/audio-spec.md) |
| Adding a stage / boss / weapon to an existing game | [checklists/new-stage.md](checklists/new-stage.md), [checklists/new-boss.md](checklists/new-boss.md), [checklists/new-weapon.md](checklists/new-weapon.md) |
| Hitting a weird bug (jitter, eaten jumps, stuck knockback...) | [gotchas.md](gotchas.md) — check here FIRST; most feel bugs are numbered entries |

## Workflow A — starting a new game from zero

1. **Pin the fantasy.** One paragraph: protagonist, setting, 8 boss archetypes
   (use the Frost/Flame/Storm/Volt/Stone/Toxin/Blade/Gravity template cycle in
   [design/mechanics.md](references/design/mechanics.md) as scaffolding, then
   rename/retheme to the game's own fiction). Run the IP checklist in
   [design/authenticity-and-ip.md](references/design/authenticity-and-ip.md).
2. **Project setup.** Follow [godot/project-setup.md](references/godot/project-setup.md)
   top to bottom: viewport 256×224, integer scaling, nearest filtering, 60 Hz
   physics, InputMap, autoloads (GameState / SaveManager / AudioManager /
   WorldFlags), collision layer table. Do not improvise these — pixel-perfect
   config is all-or-nothing.
3. **Movement core first.** Run the quickstart at the end of project-setup.md:
   test room + [player_controller.gd](references/godot/templates/player_controller.gd)
   + [camera_controller.gd](references/godot/templates/camera_controller.gd),
   using the tunables table in [design/game-feel.md](references/design/game-feel.md)
   verbatim as the starting values. **Gate: do not build content until
   run/jump/dash/dash-jump/wall-kick feel right in the test room.** Tune only
   the numbers the table marks as tunable; test the dash-off-ledge and
   buffered-jump cases explicitly.
4. **Combat core.** Add buster + charge tiers per [godot/combat.md](references/godot/combat.md)
   (pooled projectiles, hurtbox/hitbox, 3-shot cap), one placeholder enemy
   from `enemy_data.gd`.
5. **Vertical slice: the intro stage.** Build it per the intro-stage section
   of [design/level-design.md](references/design/level-design.md) — it
   teaches every verb and ends with a scripted easy miniboss. This slice
   forces stage loading, checkpoints, death/respawn, HUD, and one boss-lite
   fight to exist.
6. **First real boss + weapon.** Use the worked example in
   [design/boss-design.md](references/design/boss-design.md) and the
   new-boss + new-weapon checklists. Wire: defeat → get-weapon jingle →
   WeaponData granted → WorldFlags set → save.
7. **Scale to 8 stages.** Stage select screen, then repeat
   [checklists/new-stage.md](checklists/new-stage.md) per stage — one gimmick
   each (list in level-design.md), cross-stage WorldFlags effects for at
   least 2 stage pairs. Validate the weakness cycle
   ([checklists/new-weapon.md](checklists/new-weapon.md), integrity section)
   every time a weapon lands.
8. **Progression + polish.** Armor capsules, heart tanks, sub-tanks per
   [design/progression.md](references/design/progression.md); parallax,
   palettes, jingle set per [design/snes-authenticity.md](references/design/snes-authenticity.md)
   and [assets/audio-spec.md](assets/audio-spec.md).
9. **Before every milestone build:** sweep [gotchas.md](gotchas.md) as a QA
   checklist — each numbered entry is a known shipping bug in this genre.

## Workflow B — extending an existing game

1. **Locate the data layer.** Everything content-side should be a Resource
   (`WeaponData`/`EnemyData`/`StageData`/`BossData`). If the game predates
   this skill and hardcodes content, first refactor the one content type you
   are touching to data per [godot/data-resources.md](references/godot/data-resources.md)
   — don't bolt a hardcoded boss onto a data-driven game.
2. **Run the matching checklist** — [new-stage](checklists/new-stage.md),
   [new-boss](checklists/new-boss.md), or [new-weapon](checklists/new-weapon.md).
   They are ordered; do the steps in order and don't skip the playtest gates
   at the end.
3. **Re-validate global invariants** the addition can break: weakness-cycle
   integrity (every boss weak to exactly one weapon, chart still one cycle),
   WorldFlags read/write pairs (a flag someone sets must have readers, and
   vice versa), save schema (new upgrade/boss must round-trip), projectile
   pool sizing (new weapon's worst-case on-screen count).
4. **Feel changes** (tweaking jump/dash numbers) are not "extensions" — treat
   them as re-running Workflow A step 3: change values in one place (the
   exported tunables), retest the interaction cluster in
   [design/game-feel.md](references/design/game-feel.md), and sweep the
   movement entries of [gotchas.md](gotchas.md).

## Non-negotiables (why they're rules)

- **All gameplay logic in the 60 Hz fixed tick.** Frame-rate-coupled logic
  breaks feel numbers that were tuned in ticks (coyote 0.08 s ≈ 5 ticks).
- **Charging is orthogonal to locomotion.** A parallel action layer, never
  extra FSM states — otherwise every new locomotion state multiplies by every
  charge state ([design/architecture.md](references/design/architecture.md)).
- **Content is data, not code.** A new boss must be creatable without editing
  a `.gd` file beyond registering its data resource.
- **Original IP only.** Reproduce systems, never assets or names.
