---
name: skill-snes-rpg
description: >-
  Design and build turn-based, SNES-era JRPGs (ATB combat, party-based stat
  systems, tile overworlds, random encounters, retro pixel-art UI) in the style
  of 16-bit classics like Final Fantasy VI. Covers the full genre stack: active
  time battle gauges, per-character signature commands, an equip-to-learn magic
  system, elemental affinities and status ailments, scripted enemy AI with
  HP-threshold phases, tile-based overworld + towns + dungeons, step-counter
  random encounters with grace periods, menu-driven UI, save systems, a
  mid-game world-state twist, fully synthesized chiptune audio (Web Audio, no
  asset files), and palette-limited pixel-art rendering on HTML5 Canvas — with
  a porting note for Godot 4. Everything content-side is data-driven JSON with
  schemas and load-time validation. USE THIS SKILL whenever the user mentions a
  JRPG, turn-based RPG, ATB or active-time-battle, retro / 16-bit / SNES-style
  RPG, Final-Fantasy-style game, pixel-art RPG, tile-based overworld with
  random encounters, party-based stat or job system, an equip-to-learn magic
  system, or just describes the mechanics ("a game where characters wait for a
  bar to fill then pick Fight/Magic/Item", "a retro RPG with towns, dungeons
  and an airship") without naming the genre. Prefer this over improvising —
  the numbered rules here are the bugs and design traps every first ATB
  implementation hits.
metadata:
  version: 1.0.0
---

# SNES-Era JRPG Builder

Dense playbook for building a complete turn-based 16-bit-style JRPG. Models the
**systems** of the genre (ATB combat, signature commands, equip-to-learn magic,
tile exploration, the two-act world twist) with entirely **original
terminology** — never reuse Final Fantasy or other franchise names for
characters, spells, summons, enemies, or places. "ATB" and "JRPG" are generic
industry terms and fine to use.

## Target architecture

**Default: single-file HTML5 Canvas + vanilla JS + Web Audio.** No build step,
no external assets, runs offline from a double-click. All music and SFX are
synthesized (oscillators + ADSR); all sprites are drawn to canvas from
palette-limited pixel data or procedural draw calls.

**Data-driven, non-negotiable:** every character, enemy, spell, item, command,
and map lives in JSON data (inline `const DATA = {...}` blocks in the
single-file build, separate `.json` files in a larger build) — never hardcoded
in logic. Schemas for all six data files are in
[reference/data-schemas.md](reference/data-schemas.md).

**Godot 4 port note:** the same architecture maps cleanly — data JSON →
`Resource`/dictionaries loaded in `_ready()`, the battle and overworld state
machines → two scenes with their own state enums, canvas tile blit →
`TileMapLayer`, Web Audio synth → `AudioStreamGenerator`. Keep the data files
identical so content is engine-portable. HTML5 is the default unless told
otherwise.

## Reference files — read when needed

- [reference/battle-system.md](reference/battle-system.md) — read when
  implementing combat: ATB math, command menus, damage formulas, elemental
  precedence, status ailments, enemy AI script tables, rewards/leveling.
- [reference/exploration-and-encounters.md](reference/exploration-and-encounters.md)
  — read when implementing the overworld, towns, dungeons, vehicles, encounter
  tables, or the two-act world twist.
- [reference/data-schemas.md](reference/data-schemas.md) — read before writing
  ANY content data: JSON Schema + filled example for characters, enemies,
  spells, items, commands, and maps, plus the load-time validator contract.
- [reference/audio-and-visual-style.md](reference/audio-and-visual-style.md) —
  read when implementing music/SFX synthesis or the sprite/palette/tile
  rendering layer.

## Stated defaults (decide these FIRST, out loud)

These are explicit defaults, not ambient assumptions. State them to the user at
the start; change only on request.

1. **Save model: save-points + overworld saves.** Saving is allowed anywhere on
   the world map and at save sigils inside dungeons — never mid-dungeon
   elsewhere, never in battle. This is the genre-standard difficulty knob; a
   save-anywhere game must be rebalanced (harder dungeons, meaner bosses).
2. **ATB mode: "Wait".** Gauges pause while any player menu is open or an
   animation is resolving. An "Active" mode (gauges keep filling in menus) may
   be offered in Config, but Wait is the default and the one you test against.
3. **Party size: 4 active** from a roster of 8–14; Formation menu sets order;
   back row takes/deals reduced physical damage.
4. **Magic acquisition: Glyphstones.** An equippable relic that (a) teaches a
   fixed spell list via Glyph Points (GP) earned from battles and (b) grants a
   small stat-growth bonus on level-ups while equipped. Schema in
   data-schemas.md. Invent your own flavor name per game if you like, but keep
   this exact mechanical shape.
5. **Two acts.** A single world-state field `epoch: "verdant" | "sundered"`
   flips mid-game and swaps map set, shop stock, encounter tables, and roster
   availability. It is data, not branched code.

## Build workflow

Phase the build so something is playable at every step:

1. **Data first.** Write the six data blocks with 2–3 entries each, plus the
   schema validator. Run validation before any game code exists.
2. **Battle vertical slice.** ATB loop + Fight/Item vs one enemy, vector-drawn
   placeholders, victory/defeat states. (This is what
   [examples/atb-loop-demo.html](examples/atb-loop-demo.html) demonstrates —
   open it in a browser to see the target shape of the loop.)
3. **Full combat.** Magic + MP, signature commands, elements, statuses, enemy
   AI tables, flee, rewards, level-up.
4. **Exploration slice.** One town + one dungeon + overworld strip; tile
   rendering, collision, warps, NPC dialogue, chests, shops, inn, save sigil.
5. **Encounters.** Step-counter triggers with grace periods, per-zone tables,
   battle↔field transitions.
6. **Menus + save.** Out-of-battle menu (Item, Magic, Equip, Status, Formation,
   Config, Save), full serialization.
7. **Audio + visual pass.** Synth themes (title/overworld/battle/victory) and
   SFX, real sprite pixel data, palette discipline.
8. **The twist + content fill.** Flip `epoch`, author act-two data, roster
   changes, endgame.

Use TaskCreate to track these phases — this is always a ≥3-step build.

## Hard-Won Rules

### ATB & battle flow

**1. Pause every ATB gauge while a menu is open or an animation is resolving.**
In Wait mode, `tick()` must check a single `battleState` and skip ALL gauge
fills unless it is `"TICKING"`. Letting gauges fill under an open menu is the
single most common ATB bug — it produces input pile-ups and turn skips.

**2. Validate the actor AND the target at execution time, not selection time.**
A queued action's actor may be dead, petrified, or confused by the time it
fires, and its target may already be dead. Re-check both; retarget
single-target attacks to a living enemy, cancel actions from dead actors.

**3. One action resolves at a time — queue, don't interleave.**
Ready actors enter a FIFO action queue. Never resolve two animations
concurrently; damage application, death checks, and counter triggers happen in
a strict sequence per action.

**4. Check victory/defeat only at action boundaries.**
Evaluate end-of-battle after each fully resolved action, never mid-animation.
A poison tick that kills the last enemy must still fire the victory sequence.

**5. Clamp the gauge, don't overflow it.**
`atb = min(atb + speed * dt, READY)`. Overflow banking silently breaks turn
order fairness and makes Speed stats meaningless above a threshold.

### Damage, elements, statuses

**6. Elemental precedence is immune > absorb > resist > weak > normal — enforce it as an ordered check.**
An enemy flagged both weak and immune to fire takes 0. Implement as a single
function with early returns in that exact order; never sum modifiers.

**7. Separate physical and magical mitigation completely.**
Physical uses Attack vs Defense; magical uses Magic vs Spirit/M.Defense. A
"Defend" command halves physical only. Mixing the two makes every hybrid boss
unbalanceable.

**8. Status ailments get a save chance and a visible cue.**
Every infliction rolls `chance × (1 − target resist)`; every active status has
an icon/palette tint. Silent statuses are indistinguishable from bugs.

**9. Instant-death and petrify respect boss immunity by data, not by code.**
Bosses carry `"immune": ["doom", "stonecurse"]` in their JSON. Hardcoded
`if (isBoss)` checks always miss the one mini-boss you forgot.

### Encounters & exploration

**10. Grace period after every map entry AND every battle exit.**
Zero the step counter and add a flat 4–8 free steps before the next encounter
roll. Instant re-encounters are the #1 player complaint in the genre.

**11. Encounter tables are per-zone data with weights, not global.**
Each map region references an encounter table id: list of enemy formations
with weights and a step threshold `base ± variance`. Tuning happens in data.

**12. Decouple the battle loop and overworld loop state machines.**
Two independent state machines; a transition function suspends one and starts
the other. Input handlers are registered/unregistered on transition — a
pause in one must never leak input into the other (menu confirm on the field
must not queue a battle command).

**13. Warps and vehicle rules live in map data.**
Doors, stairs, and world↔local transitions are warp entries in `maps.json`.
Vehicle passability (what tile types the ship/skyskiff can cross or land on)
is a per-tile-type flag set, not special-cased coordinates.

### Data & progression

**14. Schema-validate every data file at load; fail loudly, on screen.**
Validate all six data files against their schemas before the title screen
renders. Print the file, path, and reason on a visible error screen — a silent
bad-JSON failure three screens into a session is the worst way to lose an hour.

**15. All cross-references are ids, and the validator resolves them.**
Spells reference element ids, Glyphstones reference spell ids, formations
reference enemy ids, shops reference item ids. The validator checks every id
resolves. Dangling references are load-time errors, not runtime crashes.

**16. Derived stats are recomputed, never stored.**
Store level, base stats, equipment ids, and Glyphstone growth history. Max HP,
effective Attack, etc. are pure functions of those. Storing derived values
guarantees save-file drift after any balance patch.

**17. The two-act twist is one data flag.**
`epoch` selects which map set, shop inventories, encounter tables, and roster
entries are active. Never `if (afterTwist)` scattered through logic — every
epoch-dependent record carries an `epoch` field ("verdant", "sundered", or
"both") and lookups filter on the current value.

**18. Level curve uses diminishing softcaps.**
EXP-to-next grows superlinearly; stat gains per level shrink past a soft cap
(e.g. ~90% of growth by level 60 of 99). Prevents both trivializing endgame by
grinding and useless late levels.

### UI, save, input

**19. Debounce menu navigation; separate "pressed" from "held".**
Track key-down edges, not key state, for cursor moves and confirm/cancel; add
repeat-delay for held directions. Raw key-state menus skip 3 items per tap at
60fps.

**20. The text box is input-gated and page-breaking.**
Text renders at a configurable chars-per-frame rate; overflow page-breaks with
a "more" indicator; advance requires a fresh confirm press (rule 19). A
confirm held from the previous box must not skip the next one.

**21. Save = complete serializable game state, versioned.**
Roster (levels, base stats, equipment, learned spells, GP progress),
inventory, currency, story/quest flags, `epoch`, current map + tile position +
facing, vehicle states, playtime, and a `saveVersion` int. If any of these
lives outside the state object, saves will corrupt.

**22. Never trust the save blob either — validate on load.**
Run the same schema discipline on loaded saves; on mismatch, show a clear
"incompatible save (v2, expected v3)" message instead of half-loading.

### Audio & visuals

**23. Synthesize all audio; own every note.**
Web Audio oscillators + ADSR envelopes for themes and SFX. No soundfonts, no
sampled files — nothing to license, nothing to load. Recipes in
audio-and-visual-style.md.

**24. One music director, crossfade on state change.**
A single module owns "what's playing"; battle entry/exit requests a track
switch and the director handles stop/start (and restores field music AFTER
the victory fanfare finishes, not concurrently).

**25. Palette discipline: 16–32 colors total, defined once.**
All sprites and tiles index into named palette banks. This is what makes it
read as 16-bit; ad-hoc hex colors sprinkled through draw calls is what makes
it read as programmer art.

## Pre-Build Checklist

Before writing game code, confirm:

- [ ] Stated the five defaults (save model, ATB Wait, party size, Glyphstone
      mechanic, two-act epoch flag) to the user
- [ ] Target confirmed: single-file HTML5 (or Godot 4 port explicitly requested)
- [ ] All six data schemas copied in and the load-time validator written first
- [ ] Original names invented for: game world, all characters, all spells, all
      signature commands, the Glyphstone flavor name, all enemies, all places —
      zero franchise proper nouns
- [ ] Roster plan: 8–14 characters, each with exactly one unique signature
      command (see commands.json schema)
- [ ] Encounter zones sketched with grace-period values
- [ ] TaskCreate list matches the 8 build phases

## Post-Build Validation

Before calling the build done:

- [ ] Load with a deliberately broken JSON entry → visible schema error screen
      naming file + path (rule 14), not a blank page
- [ ] Open a battle menu and wait 10 seconds → no gauge movement, no queued
      turns burst (rule 1)
- [ ] Kill an actor whose action is queued, and kill a target mid-queue →
      action cancelled / retargeted, no crash (rule 2)
- [ ] Enemy that is weak+immune to the same element takes 0 (rule 6)
- [ ] Enter a map and exit a battle → verified 4–8 encounter-free steps both
      times (rule 10)
- [ ] Hold confirm through a dialogue box → next box does NOT auto-skip
      (rules 19–20)
- [ ] Save → reload from a fresh page load → position, party, inventory,
      flags, epoch, playtime all intact (rule 21)
- [ ] Flip `epoch` via a debug key → maps, shops, encounters, roster all swap
      with no code edits (rule 17)
- [ ] Victory fanfare plays to completion, then field music resumes (rule 24)
- [ ] Grep the entire output for franchise proper nouns (character/spell/
      summon/enemy/place names) → zero hits
- [ ] Runs from a double-clicked `.html` file with no server, no console errors
