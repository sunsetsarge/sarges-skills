# Spritesheet Spec — Guidance, Not Art

This document specifies the **grid, animation list, palette discipline, and export conventions** an artist or AI image pipeline must hit for the player and enemy sheets. It does not contain art direction (that is a separate visual-style pass) — it exists so any sheet dropped into `references/godot/templates/` slots into the state machine and `AnimatedSprite2D`/`AnimationPlayer` setup without rework.

## Player frame grid

- **Frame cell: 48x48 px**, uniform grid, every animation on the same cell size. Do not vary cell size per animation — Godot `SpriteFrames`/`AtlasTexture` regions and hitbox-authoring both assume a fixed cell.
- **Visual character height ~30px** inside that 48x48 cell. This is deliberate MMX-scale proportion: the extra cell space is headroom for jump/dash poses, weapon overlays, and charge-aura overlays that extend beyond the idle silhouette without clipping or forcing a larger cell everywhere else.
- Internal game resolution is 256x224 (see `references/design/game-feel.md`) — a 48px-tall character reads as roughly 1/7th screen height, matching genre proportion (small-headed, long-legged action-platformer silhouette, not chibi-proportioned).
- Author on a **grid, left-aligned per frame**, consistent origin (see Origin rule below). Do not hand-crop frames to bounding box — that breaks fixed-cell playback timing in engine.

## Required animation list

Every state below must exist as its own strip (or be covered by the overlay trick, see next section). Frame counts are targets, not hard limits — adjust for readability, not padding.

| Animation | Frames | Loop? | Notes |
|---|---|---|---|
| Idle | 3-4 | Loop | Include a blink/breathing-tell frame so idle isn't a single static pose; this is the frame the player stares at most. |
| Run | 8-10 | Loop | Classic action-platformer run cycles read best at 8+ frames for the "run cycle" feel MMX-scale games use; fewer than 6 reads as a treadmill shuffle. |
| Jump rise | 2 | No (hold last) | Launch pose, then a rising-arc pose held until apex or fall triggers. |
| Apex | 1 | No (hold) | Brief peak-of-arc pose — many implementations skip this and get a jarring rise-to-fall snap; even 1 frame smooths it. |
| Fall | 2 | Loop | Falling pose(s), loop while airborne and descending. |
| Land | 2 | No | Plays once on grounded transition. Per the "no landing recovery" rule in `game-feel.md`, this is **purely cosmetic** — it must not add an input-lock frame; control returns same tick as the grounded flag. |
| Dash | 2 + dust | Loop (dash) / one-shot (dust) | Dash pose loops for dash duration; dust-kick is a separate one-shot overlay/particle-style strip triggered on dash start, not looped with the pose. |
| Wall-slide | 1-2 | Loop | Slower playback rate than run — sells the reduced wall-slide fall speed (see `game-feel.md`). |
| Wall-kick | 2 | No | Launch-off-wall pose, held briefly into the resulting Jump/Fall strip. |
| Hurt | 2 | No (hold for i-frame duration) | Held/blinking for the full 1.0s i-frame window (see `gotchas.md` #7 for the state-machine trap this creates). |
| Death burst | 6-8 | No | Explosion/burst-style death sequence, single play then hide/respawn. |

### Shoot overlays — the torso-swap trick

Every locomotion state (Idle, Run, Jump, Fall, Dash, Wall-slide) needs a "shooting" variant so the player can fire while moving, jumping, dashing, etc. **Do not hand-draw a full duplicate strip per state** — that multiplies sheet size by ~2x for zero new silhouette information below the waist.

Instead:

1. Split the character rig conceptually into **lower body (legs/hips)** — driven entirely by the locomotion strips above — and **upper body/arm (torso + buster arm)** — driven by a small, separate set of torso poses: *arm-down* (default) and *arm-raised/aiming* (shooting).
2. Author only the **arm-raised torso** as a second layer per relevant pose (idle-aim torso, run-aim torso, jump-aim torso, etc.) — these are short strips (often just 1-2 frames each, since the arm pose barely changes across a locomotion cycle) composited over the existing lower-body frames at runtime, or pre-baked as a second row per animation if the target engine can't do runtime layering cheaply.
3. In Godot, the cheap version is two `AnimatedSprite2D` nodes (or a `Sprite2D` + shader-free layered draw) — `body` node plays the full locomotion strip, `arm_overlay` node plays a short aim-pose strip only when `is_shooting` is true, pinned to the same origin. This avoids doubling every strip while still giving every state a shooting variant.
4. If runtime layering is not viable for the target pipeline (e.g., strict single-sprite-per-frame export requirement), pre-bake the overlay by duplicating only the torso region into a parallel "-aim" strip per animation, keeping legs identical — still far cheaper to draw than a fully independent shooting animation set.

### Charge aura overlay

- **4-frame loop**, additive-blend-friendly (bright core, soft falloff), authored as its own small strip independent of body pose — same layering approach as the shoot overlay: a separate node/layer pinned to the buster-hand anchor point, visible during Lv2/Lv3 charge tiers (see `game-feel.md` charge tier table), not baked into every locomotion strip.
- Color-code the aura to the two charge tiers if the design calls for a visible tier distinction (e.g., yellow at Lv2, blue/white at Lv3) — this is a readability requirement, not just polish, since charge tier changes player and enemy risk calculus in real time.

### Projectiles

| Sprite | Frames | Notes |
|---|---|---|
| Buster shot (uncharged) | 2 | Small, fast-traveling, simple 2-frame flicker/pulse is sufficient — this is the highest-frequency sprite on screen, keep it cheap. |
| Charged shot | 3-4 | Larger, more frames justified since it's rarer and meant to read as "invested" — include a brief muzzle/spawn frame distinct from the sustained travel frame(s). |

## Enemy sizes

| Class | Size | Notes |
|---|---|---|
| Small (fodder) | 16x16 | Screen-filler enemies, walkers/turrets; keep frame count low (2-4 per animation) since many will be on screen at once — budget-conscious for both art time and runtime sprite count. |
| Medium (standard) | 32x32 | Most named regular enemies. |
| Mini-boss | 48-64 | Mid-stage checkpoint gate enemies; large enough to read as a threat step-up from mediums without needing full boss-arena staging. |
| Boss | 64-96 | Full stage/BossData-driven bosses (see `checklists/new-boss.md`); at this size, plan for multi-part sprites (body + weak-point overlay) rather than one monolithic sheet if the design calls for a separately-targetable weak point. |

Enemy sheets follow the same fixed-cell-grid and per-entity-single-sheet rules as the player.

## Palette guidance

- **~15 colors + transparency per sprite**, consistent with actual SNES 15-color-per-4bpp-tile hardware limits. This is not a nostalgia-only constraint — it forces readable, high-contrast silhouettes, which matters more at 256x224 than at modern resolutions where detail can hide.
- **Shared master ramps**: build one limited master palette per major color family (skin/metal/weapon-energy/environment) and pull every sprite's shading from those shared ramps rather than freehand-picking new colors per sprite. This keeps palette-swap-based enemy recolors (common in this genre for reused enemy bodies with new elemental tint) trivial — swap ramp reference, not repaint pixels.
- **Hue-shift shading, not black-shading**: shadows should shift the base hue toward a cooler/darker adjacent hue (e.g., orange base -> red-brown shadow, not orange -> black-orange). Straight black-mixed shading reads muddy and flat at small pixel counts; hue-shifting is the specific technique that gives SNES-era sprites their characteristic vibrancy.
- **1px dark outline convention**: every sprite gets a consistent 1px outline, using a dark-but-not-pure-black outline color (usually a very dark shade of the sprite's own dominant hue, or a shared near-black outline color used workspace-wide) so silhouettes separate from background tiles at a glance. Do not mix outlined and non-outlined sprites in the same scene — pick the convention once and hold it everywhere, player and enemies alike.

## Export conventions

- **Single sheet per entity** — one PNG per player, per enemy type, per boss, not scattered per-animation files. This matches how Godot `SpriteFrames` resources and `AtlasTexture` region definitions expect to consume art, and keeps the on-disk asset count sane across 8 stages x several enemies each.
- **JSON or Godot AtlasTexture region metadata accompanies every sheet** — explicit `[x, y, width, height]` regions per frame per animation, not "assume a fixed grid and hope." Even though the grid is fixed-cell, explicit regions catch authoring drift (an artist nudging a frame) before it becomes a runtime bug.
- **Origin at feet-center**: every frame's logical origin/pivot is the point directly between the character's feet, at ground contact height — not the cell's geometric center, not top-left. This is what makes grounded-position math (`position.y` == floor height) and collision-shape alignment consistent across every animation frame, including ones where the character's silhouette shifts up/down within the cell (crouch, wall-slide, jump apex).

## Pivot / facing rule

- **Author every sprite facing right.** Left-facing is produced at runtime via `flip_h` (or equivalent horizontal mirror), never hand-drawn as a separate mirrored strip. This halves art volume and guarantees left/right are pixel-identical mirrors (important for fair hitboxes).
- **Watch the asymmetric buster arm.** The buster/weapon arm is not symmetric left-to-right on a real character (it's usually forward-extended on one side), so a naive `flip_h` on the whole sprite is fine for the body silhouette but will flip the arm's screen-space X offset along with it — which is actually correct for the arm sprite itself, but **breaks the shot-spawn origin** if that origin is hardcoded as a fixed local-space offset rather than recomputed per facing.
  - **The fix**: store the shoot-origin/muzzle anchor as a named `Marker2D` (or equivalent) child of the sprite, authored once for right-facing. When facing flips, either (a) let the marker inherit the parent's `flip_h`/negative-scale-X so its local offset mirrors automatically, or (b) if the engine/rig doesn't propagate mirroring to child transforms cleanly, explicitly negate the marker's local X offset when facing is left. Verify this with a visual test at both facings before shipping any weapon — an un-mirrored muzzle anchor is the single most common "shots spawn from the wrong side of the sprite" bug in this genre (see `gotchas.md` for the related hitbox version of this issue).
