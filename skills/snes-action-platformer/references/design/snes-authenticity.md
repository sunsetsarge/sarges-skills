# SNES Authenticity

This file covers the presentation-layer constraints that make a game *read* as authentically 16-bit-era, independent of the underlying engine. None of these are hard technical limits on a modern engine — they are deliberate creative constraints worth keeping because they're what the eye and ear recognize as "SNES," and because constraints like these tend to produce better, more legible readability than an unconstrained modern renderer defaults to.

## Internal resolution: 256 x 224

Render the actual game world at 256 x 224 pixels internally, then scale that framebuffer up to the display using **integer scaling only** (2x = 512x448, 3x = 768x672, 4x = 1024x896) — never a non-integer stretch.

Why this matters:

- **Integer scaling** keeps every source pixel mapping to a whole number of output pixels, so pixel art stays crisp with hard edges — non-integer scaling causes uneven pixel sizes across the image and visible shimmer/wobble during scrolling, which instantly reads as "wrong" to anyone familiar with the era.
- **UI safe areas**: design HUD elements (HP bar, weapon icon, ammo meter) with a small margin from the 256x224 edge, since some display setups (especially if any overscan-style border treatment is used, or on certain aspect-ratio letterboxing choices) can crop a few pixels at the frame edge. A margin of 4-8px from any edge is a safe default for critical UI text/icons.

## Palette discipline

- **Per-sprite palettes of roughly 15 colors + 1 transparency index** (16 total slots, matching the classic 4bpp indexed-color convention) — this is a creative discipline worth keeping even without hardware forcing it, because it forces cohesive, readable sprite silhouettes instead of an unconstrained-palette gradient soup that's harder to read at small size and low resolution.
- **Limited master palette**: keep the *game's* total palette (across all sprites and backgrounds) to a curated, cohesive set of color ramps rather than an unbounded color space — pick a handful of ramps (e.g., a warm ramp, a cool ramp, a neutral/skin ramp, a couple of accent ramps) and draw all art from those ramps. This is what gives an SNES-era game its distinctive "unified" look rather than looking like a patchwork of unrelated assets.
- Each ramp should have enough steps (typically 4-6 shades from darkest to lightest) to shade form/volume convincingly within the per-sprite budget, without needing more total colors than the budget allows.

## Layered parallax backgrounds

Use at least **3 background layers** with distinct scroll ratios relative to the camera/foreground:

| Layer | Scroll ratio | Notes |
|---|---|---|
| Foreground/gameplay layer | 1.0 | Moves exactly with the camera — this is the layer the player and collision geometry live on. |
| Mid-background | 0.5 | Scrolls at half camera speed, reading as "further away." |
| Far background | 0.25 | Scrolls at a quarter camera speed. |
| Sky/backdrop | ~0 (near-static) | Effectively fixed or drifting extremely slowly — reads as infinitely distant. |

More than 3 background layers is fine and common (SNES-era games often used 4+), but 3 is the minimum to sell convincing depth. Keep ratios strictly decreasing from foreground to sky — an inconsistent ordering (a "closer" layer scrolling slower than a "further" one) breaks the depth illusion immediately.

## Per-scanline sprite limits as a design discipline

Authentic SNES hardware had real per-scanline sprite limits that caused visible flicker when exceeded. On modern engines there's no hardware forcing this, but **keep it as a deliberate design discipline anyway**:

- **Cap simultaneous enemies/projectiles on screen to roughly 8-10.** This isn't a performance necessity on modern hardware — it's a *readability* necessity. A boss fight or enemy gauntlet with 30 unmanaged hazards on screen at once stops being a fair, readable challenge and becomes visual noise the player can't parse in time to react, which directly undermines the telegraphing discipline in `boss-design.md`.
- **Flicker is authentic but optional.** If you want the specific period-authentic look of sprites flickering/alternating when a scanline's object budget is exceeded, it's fine to simulate deliberately as an aesthetic choice — but don't rely on it as your only overflow-handling strategy, since it can read as a bug to players unfamiliar with the era. A hard cap (oldest projectile despawns, or new spawns are queued/blocked) is a safer default; flicker can be layered on top as flavor.

## Locked 60 fps

Run and target a locked 60 fps presentation, matching the 60 Hz fixed tick from `game-feel.md`. This genre's precision platforming (frame-perfect coyote windows, telegraph frame counts, hit-stop timing) is specified in frame counts throughout this skill's docs precisely because 60 fps is assumed as a constant — a variable or lower framerate breaks the felt timing of every tuned value in this skill.

## SPC-style audio

Aim for a **chiptune / sampled hybrid** sound — short sampled instrument waveforms (not full studio-recorded tracks) run through a synthesizer-style voice architecture, roughly **8 simultaneous voices** as a period-authentic polyphony budget, with a signature **echo/reverb character** (a distinct short-decay echo effect applied project-wide) that's instantly recognizable as SNES-era soundtrack texture. This is achievable on any modern audio engine — the target is the *timbre and voice-count discipline*, not literal hardware emulation.

### Required jingle list

These short musical stingers are genre-conventional and expected — treat this as a checklist, since missing one (especially get-weapon or boss-intro) will be conspicuous to players familiar with the genre:

- **Stage-select** theme (plays on the stage-select screen, often with a distinct loop per selectable stage or one shared theme).
- **Get-weapon fanfare** (plays immediately after defeating a boss, accompanying the weapon-grant moment — see `mechanics.md` and `boss-design.md`).
- **Boss-intro sting** (short, sharp musical hit accompanying the ritual intro sequence's name-splash beat — see `boss-design.md`).
- **Checkpoint** jingle (brief confirmation sting when a checkpoint is reached/saved).
- **Death** jingle (plays on player death, short and distinct from game-over).
- **Game-over** jingle (plays when all lives/continues are exhausted, distinct and more final-sounding than the death jingle).
- **Victory / stage-clear** fanfare (plays after a stage's final boss is defeated and the stage is marked complete).

## Screen-shake and hit-stop as feel seasoning

- **Hit-stop**: freeze gameplay (or slow it drastically) for **2-4 frames** on charged/heavy hits — this tiny pause is what gives a charged shot or a weakness hit a sense of weight and impact on modern displays; skipping it makes even a mechanically-correct heavy hit feel weightless.
- **Screen-shake**: reserve for genuinely large moments (boss phase transitions, big explosions, boss defeat) rather than every hit — overusing screen-shake degrades its impact and can actively hurt readability of a fast-paced fight if the camera never holds still. Keep shake amplitude small and short (a few pixels of offset, a few frames of duration) even on "big" moments — this is seasoning, not a physics effect.
