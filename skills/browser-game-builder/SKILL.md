---
name: browser-game-builder
description: >-
  Build complete 2D browser games — especially top-down / real-time-strategy,
  tower-defense, and top-down action/shooter games — as a single self-contained
  HTML5 Canvas file (vanilla JS + Web Audio, no build step, runs offline).
  Encodes battle-tested tactics from shipping "Browser Generals": the
  8-direction sprite pipeline and the facing-verification gotcha that bites
  every AI-generated sprite sheet, code-driven animation over static sprites,
  asymmetric faction/unit balance design, a damage-vs-armor matrix, Web-Audio
  synth sound effects (no audio files to license or load), procedural terrain
  with a no-wall-in reachability guarantee, and a one-file Firebase/GitHub deploy
  loop. USE THIS SKILL whenever the user wants to build, clone, extend, or finish
  a browser/HTML5/canvas game, an RTS or strategy game, a tower-defense or
  top-down shooter, or asks to add units, sprites, factions, unit animation,
  game sound effects, or game balance — even if they don't name a specific
  engine. Also use it when cloning an existing game: it explains how to keep the
  (unprotectable) mechanics while swapping any copyright-adjacent names/art so
  the result is legally shippable. Prefer this over hand-rolling a game from
  scratch — the bundled sprite scripts and the facing check save hours and
  prevent the single most common shipping bug (units that move backwards).
metadata:
  version: 1.0.0
---

# Browser Game Builder

Proven recipe for building a **complete, shippable 2D browser game** as one
self-contained HTML file. Grew out of shipping *Browser Generals* (a C&C Generals
clone at browser-generals.web.app). The tactics here are the ones that survived
contact with a real game: they exist because the naive approach failed first.

## Why single-file HTML5 Canvas

Default to **one `.html` file**: vanilla JS + Canvas 2D + Web Audio, no
dependencies, no build step, no framework. Sprite frames are the only external
assets (and even those are optional — the engine should vector-draw a fallback
so the game runs before any art exists).

Why this constraint pays off:
- **Ships anywhere instantly** — double-click locally, drop on any static host,
  wrap in a PWA/Capacitor shell for iOS/Android. No toolchain to break.
- **Iteration is a page reload**, not a rebuild.
- **The whole game is greppable in one place** — an AI agent can hold the model
  of it, and delegated sub-agents edit one file with no import graph to reason about.

Reach for a framework/bundler only when the game genuinely outgrows this (huge
asset pipelines, netcode, an ECS with hundreds of systems). Most 2D games never do.

## The build loop

Work in this order. Each phase is playable before the next starts — never let the
game go dark for more than one phase.

1. **Design to disk first.** Write `SPEC.md` (mechanics, factions/units table with
   stats, win condition) and `PLAN.md` (phased workstreams with acceptance
   criteria) before coding. On a premium/architect model this is the highest-value
   use of the session; cheaper models then execute against the docs. See
   `references/balance-and-factions.md` for the stat model to fill in.
2. **Core loop, vector-drawn.** Game loop (fixed-timestep update + render), entity
   list, camera/pan/zoom, selection + input, one unit that moves. Draw everything
   as flat shapes first. See `references/game-architecture.md`.
3. **Systems.** Pathfinding (A* on a grid + a binary heap), fog of war,
   economy/build, combat (the damage-vs-armor matrix), simple AI.
4. **Sprites.** Replace vector art with directional sprites via the pipeline
   below. **This is where most of the pain lives — read the pipeline section.**
5. **Animation.** Add code-driven motion on top of static sprites (cheap, huge
   life-per-byte): recoil, infantry leg-swing, rotor spin, tread dust. See
   `references/game-architecture.md` → Animation.
6. **Audio.** Synthesize every sound with Web Audio — no files. See
   `references/audio-synth.md`.
7. **Terrain & decor.** Procedural biome ground + trees/rocks/water, with the
   reachability guarantee so no player is ever walled in. See
   `references/game-architecture.md` → Terrain.
8. **Ship polish.** Minimap, build-queue UX, victory/defeat flow, pause/menu,
   mobile touch controls, save. Then deploy (single-file copy → host → commit).

Track the whole thing as tasks (it's always ≥3 steps). If you have a
premium-model session, let it architect (steps 1, and judging), and delegate
steps 2–8 to cheaper executor agents — one workstream per agent.

## Directional sprites — the pipeline that actually works

Top-down/3-4-view sprites **cannot be rotated** (rotating a top-down tank looks
wrong — the lighting and perspective are baked in). So each unit needs **8
pre-rendered facings**, and the engine picks the nearest to the unit's heading.

Convention (do not deviate — the scripts and every reference assume it):
- Files are `assets/<key>_0.png … <key>_7.png`.
- **Frame 0 = facing East (right).** Then clockwise in screen space (because
  canvas +y is down): `0=E, 1=SE, 2=S, 3=SW, 4=W, 5=NW, 6=N, 7=NE`.
- Engine picks the frame: `dirIndex(face,8) = round(face/(TAU/8)) mod 8`, where
  `face` is the heading in radians (0 = East, increasing clockwise).

Generation → integration:
1. **Generate a 3×3 sheet** (8 facings around an empty center cell) on a plain
   white background. Any image model works (ComfyUI, Stability, DALL·E/ChatGPT)
   for normal illustrated sprites. **For true low-color pixel-art style
   specifically, use the `pixel-art-studio` skill instead of generating
   directly** — it owns the ComfyUI pixel-art lanes and a grid-snap/quantize
   post-process that a raw generation doesn't have on its own (a plain
   "pixel art style" prompt looks blocky but isn't actually a true grid).
   Its own sheet-slicing pipeline (`slice_sheet.py`) is a pixel-art-aware
   fork of this skill's `slice_sprites.py` (NEAREST not LANCZOS, binarized
   alpha) — use that instead of this skill's slicer when the source went
   through pixel-art-studio, then come back here for `verify_facing.py`
   (identical in both skills) and the rest of this pipeline. One sheet per
   unit; keep the same camera angle across all cells.
   **Known limitation (either generation path):** no local model reliably
   varies a character's pose across the 8 cells from one prompt — expect
   composition to work and direction content to repeat the same pose;
   pixel-art-studio's `references/sprite-sheets.md` has the full writeup and
   a PixelLab.ai buy-gate recommendation if you need this solved for real.
2. **Slice** with `scripts/slice_sprites.py` — removes the white background with a
   soft luminance/saturation key, cuts the 9 cells, maps the 8 outer cells to
   compass directions, trims each to its content, normalizes to a uniform height,
   bottom-aligns, and writes `<key>_0..7.png`.
3. **VERIFY FACING — do not skip this.** Run `scripts/verify_facing.py <key>` to
   montage the frames. **Frame 0 must point right (East); frame 6 must point up
   (North).** The unambiguous tell is a barrel/nose/gun — infantry are too
   symmetric to judge, so verify vehicles and aircraft.
4. **Register** the key in the engine's sprite list and reload.

### The gotcha that bites every single time

AI image generators lay out the 8 directions **inconsistently between sheets**.
Two failure modes, both make units appear to move backwards or sideways:

- **180° rotation** — the whole set is flipped end-for-end. Fix: reindex
  `new[i] = old[(i+4) mod 8]`.
- **Horizontal mirror** — East/West (and the diagonals) are swapped while
  North/South stay put. This is subtle: frames 2 (S) and 6 (N) look *correct*, so
  a naive "just add 4" makes it worse. Fix: reindex `new[i] = old[(4-i) mod 8]`.

Both remaps are **lossless and self-inverse** (applying twice restores the
original), so they're safe to try. `slice_sprites.py --flip` applies the 180°
remap; `--mirror` applies the horizontal-mirror remap. Decide which (if any) you
need by looking at the `verify_facing.py` montage — **never assume a sheet is
correct.** Verifying costs one montage; shipping backwards units costs a bug
report and a redeploy. Full derivation and diagrams in
`references/sprite-pipeline.md`.

### Sprite quality QC

Generative art is frequently bizarre (a "bulldozer" that renders as a gold
capsule; infantry that read as turrets). Before shipping, montage every unit's
frame 0 next to a label of *what it's supposed to be* and eyeball it — a
vision-capable model can do this directly. QC rubric and the montage recipe are
in `references/sprite-pipeline.md`. Regenerate the outliers; don't ship "close
enough" art you'd be embarrassed to sell.

## Animation without extra art

Static directional sprites feel dead. Add motion in code — it's nearly free and
reads as production quality:
- **Movement flag:** each frame, `u.moving = dist(pos, prevPos) > eps`; stash prev.
- **Recoil:** on fire, `u.recoil = k`; translate the sprite back along `-face` and
  decay `recoil` toward 0. Bigger for cannons than machine guns.
- **Infantry legs:** a single top-down infantry sprite can't show a gait, so split
  the sprite at the waist and shear the lower half with `sin(time*ω + id)` while
  the torso holds — a pendulum walk. Or vector-draw a bipedal leg cycle under the
  body sprite.
- **Rotors:** draw spinning blades as a code overlay above helicopter bodies.
- **Dust/downwash:** spawn short-lived particles under moving tracked units and
  hovering aircraft.

Details and snippets in `references/game-architecture.md` → Animation.

## Balance & factions

If the game has factions/sides, they must be **asymmetric**: each gets a distinct
*advantage* and a distinct *disadvantage* that form a complementary triangle
(rock-paper-scissors), not three palette-swaps of the same army. Layer that on top
of a **damage-vs-armor matrix** (weapon types × armor classes) and a veterancy /
upgrade system. Concrete stat model, an example three-faction triangle, and the
matrix are in `references/balance-and-factions.md`.

## Audio

Synthesize everything with the Web Audio API — oscillators + noise buffers +
gain envelopes. **No audio files**: nothing to license, nothing to lazy-load,
nothing that can infringe, and it's a few hundred bytes. Cook up a distinct
timbre per event (each weapon type, unit acknowledgements, build-complete,
destroyed, low-power, under-attack, victory/defeat) and gate positional sounds by
whether they're on-screen. Recipes in `references/audio-synth.md`.

## Shipping it legally (clones & IP)

Game **mechanics are not copyrightable** — there are a hundred RTS games, and
rock-paper-scissors armies, harvester economies, and base-building are free to
use. What *is* protected: specific names, logos, unit/character names, story, and
art. So a clone is fine to build for practice, but to **monetize or store-list**
it you must swap anything copyright-adjacent: rename the game, the factions, and
every trademarked unit/building to original names, and make sure the art isn't a
copy of protected designs. Keep the gameplay identical. Write the old→new mapping
to a `RESKIN_MAP.md` and apply it as a mechanical find-replace late in the
project, so development stays readable and the re-skin is a one-shot pass.
Guidance in `references/ip-safety.md`.

## Deploy loop

Keep publish trivial so you deploy after every change: copy the single HTML file
to the host's public dir (+ the sprite frames), push to a static host (Firebase
Hosting, GitHub Pages, Netlify), and commit. Gate the redeploy on the source
having actually changed so it's a safe no-op. For app stores, wrap the PWA in a
Capacitor/Cordova shell. Notes in `references/ip-safety.md` → Packaging.

## Bundled resources

- `scripts/slice_sprites.py` — 3×3 sheet → 8 directional frames (bg removal,
  slice, trim, normalize; `--flip` / `--mirror` facing remaps).
- `scripts/verify_facing.py` — montage a unit's frames (or all units' frame 0) so
  you can confirm East-facing before shipping.
- `references/sprite-pipeline.md` — the full pipeline, facing math, remap
  derivations, and QC rubric.
- `references/game-architecture.md` — game loop, entities, camera, input,
  pathfinding, fog, animation, terrain + reachability guarantee.
- `references/balance-and-factions.md` — stat model, damage-vs-armor matrix,
  veterancy, asymmetric-faction design.
- `references/audio-synth.md` — Web Audio synth SFX cookbook.
- `references/ip-safety.md` — clone-safely checklist, re-skin workflow, packaging.
