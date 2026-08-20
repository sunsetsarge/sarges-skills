---
name: pixel-art-studio
description: Generate game-usable, true-grid pixel art (character sprites, tiles, icons, sprite sheets, animations) three ways -- GENERATE via the local ComfyUI install then grid-snap/quantize in Python (Lanes A/B/C), DRAW every pixel deterministically in Pillow via scripts/pixelstudio.py with no model at all (Lane D), or call the PixelLab.ai MCP tools directly for genuine 8-direction rotation + multi-frame animation (validated 2026-08-14 -- see below). Use this whenever the user asks for pixel art, a sprite, a tileset, an icon, a spritesheet, an 8-bit or 16-bit game asset, a pixel animation or GIF, or retro/SNES-style game art, even if they don't name a tool or resolution. Also use it to clean up an existing "pixel-art-ish" image (e.g. from ChatGPT/DALL-E) into a true grid, to slice a generated 3x3 direction sheet into 8 game-ready frames, to build an LPC universal spritesheet, to palette-swap variants of an existing sprite, or to STUDY a reference image and learn its style. NOT for photorealistic or non-pixel-style image generation (comfyui-studio). Direction-accurate 8-way ROTATION SHEETS are NOT reliably achievable via one-shot ComfyUI/ChatGPT generation (models fake the composition but repeat the same pose in every cell) -- say so honestly, and reach for the `mcp__pixellab__*` tools instead if available (confirmed working on the exact case that fails locally); Lane D can also hand-draw true back/side views at the cost of real token spend per sprite.
---

# Pixel Art Studio

Produces true-grid pixel art PNGs two different ways:

- **Generate lanes (A/B/C)** — generate with the local ComfyUI install (or
  ChatGPT desktop, named explicitly), then run every result through a Python
  post-process pipeline that grid-snaps, quantizes, and verifies the output --
  so "pixel art" means an actual low-resolution color-quantized grid, not an
  AI image that merely looks blocky at a glance.
- **Draw lane (D)** — no model at all. You are the artist: author a `build.py`
  that places every pixel via `scripts/pixelstudio.py` (Pillow only), render,
  **look at it**, critique, fix, repeat.

**Division of labor:** ComfyUI only generates. `scripts/pixelize.py` (this
skill) owns 100% of the pixelization — no ComfyUI custom node does grid-snap
or quantization here. This is deliberate: ComfyUI-Manager blocks node
installs on this machine, and doing pixelization in Python makes the same
pipeline work identically on ComfyUI output, ChatGPT output, or any existing
image on disk.

## The four lanes

| Lane | Model | When to use | License |
|---|---|---|---|
| **B (default for single sprites)** | `dreamshaperPixelart_v10.safetensors` (SD1.5, 512px) | Best authentic pixel-art texture, least post-processing needed | OpenRAIL — check terms before commercial use |
| **A** | Qwen-Image (via Lightning LoRA, ~1328px) | Complex scenes, stronger prompt adherence, commercial-safe | Apache-2.0 |
| **C** | ChatGPT desktop / DALL-E | **Only when the user explicitly names ChatGPT** (per `chatgpt-desktop`'s own trigger rule) — strongest stylistic quality, always off-grid | Follows OpenAI's terms |
| **D** | none — deterministic Pillow drawing | Icons, tiles, UI chrome, small sprites, palette variants, animation, true back/side views, and anything that must stay **editable** afterwards | MIT (see `THIRD-PARTY.md`) |

### Choosing a lane — read this before generating anything

**Default to A/B.** They cost GPU seconds; Lane D costs model tokens, because
every sprite is a hand-written 100–270 line build script plus 2–3
render→look→fix passes. Do not spend Lane D tokens on work a generation
handles.

Reach for **Lane D** when one of these is true:

- The asset is small and geometric — an icon, a tile, a UI frame, a HUD
  element, a health pip. Generation overshoots and then fights you.
- The user will want **edits later**. Lane D regenerates from `build.py`, so
  changing the sword leaves everything else byte-identical. A/B re-roll and
  pray.
- You need **palette-swap variants** (enemy recolors) — `replace()` per ramp
  step, seconds each.
- You need a genuine **back or side view**. Diffusion won't give you one (see
  the 8-direction section); hand-drawn code will.
- You need **deterministic animation** — the same character guaranteed across
  every frame, without Qwen-Edit's ~22-min cold load per pass.

Stay in **A/B** when the subject is ornate or high-detail (an armored knight
with 30 plate segments). Lane D has a real detail ceiling — hand-placed
primitives cannot match a diffusion render there, and `references/cleanup.md`
says so plainly. The two lanes compose: generate in A/B, then clean into an
editable Lane D `build.py` (see "Hybrid" below).

Read `references/pixel-prompting.md` before writing the prompt — "simple
background" alone does not reliably produce a flood-fill-friendly flat
background on Lane A/B; it documents what actually works, per-lane
resolution quirks, and the anti-aliasing-suppression vocabulary that applies
to all three lanes.

## Workflow

### 1. Generate

**Prefer the comfyui MCP tools** (`enqueue_workflow`, `get_history`,
`view_image`) if they're registered in this session — that's
`comfyui-studio`'s normal flow and it owns model routing, VRAM/recovery
management, and prompt expansion. Load `assets/workflows/lane-a-qwen.json`
or `assets/workflows/lane-b-dreamshaper.json`, swap the prompt text and
seed, enqueue, and verify via `get_history` (never trust the submit return
alone — same lesson as comfyui-studio).

**If the comfyui MCP tools are not available** (check with a quick
`ToolSearch` for `comfyui` — this skill's own Phase 0 build hit a session
where they simply weren't registered, not just slow to connect), fall back
to direct HTTP:

```bash
# Lane B (dreamshaperPixelart_v10) -- ad-hoc checkpoint graph
C:\AI-Shared\python.exe scripts\comfy_submit.py --checkpoint dreamshaperPixelart_v10.safetensors --prompt "pixel art, <subject>, front facing, standing pose, 16-bit SNES RPG sprite style, flat colors, no anti-aliasing, crisp pixel grid, solid single-color background, full body, game asset" -o sprite.png

# Lane A (Qwen) -- reuses assets/workflows/lane-a-qwen.json
C:\AI-Shared\python.exe scripts\comfy_submit_template.py assets\workflows\lane-a-qwen.json --prompt-node 5 --prompt "<your prompt>" --seed-node 8 --seed 7 -o sprite.png
```

Both require ComfyUI Desktop running on port 8000 (`curl
http://127.0.0.1:8000/system_stats` to check). If it's down or checkpoint
loading throws `'ModelMMAP' object has no attribute 'get_file_handle'`, see
comfyui-studio's SKILL.md failure table (`comfy-aimdo` version mismatch) —
**kill ComfyUI fully before reinstalling the fix**, a reinstall while it's
still running silently no-ops (Windows file locks).

**Lane C (ChatGPT, only when named):** use the `chatgpt-desktop` skill's
`gen_image.py` directly.

### 2. Clean the background (if the source has one)

**Try prompting harder first, before reaching for RMBG.** The acceptance test
that proved this skill hit a scenic Lane B background, tried
`comfy_rmbg.py`, and found it unreliable on a small character against a
large detailed scene (INSPYRENET only partially separated them; RMBG-2.0
barely segmented at all) — re-prompting with "isolated on plain white
background, studio background, no scenery, no trees, no building" produced
a clean flat background on the *first* regeneration, which `pixelize.py
--alpha`'s flood-fill then handled correctly. Full vocabulary in
`references/pixel-prompting.md`.

If re-prompting isn't practical (e.g. you're processing an existing image,
not regenerating), RMBG is still worth trying — it works well when the
subject reads as clearly separable from the background (INSPYRENET
outperformed RMBG-2.0 in testing, and is the script default):

```bash
C:\AI-Shared\python.exe scripts\comfy_rmbg.py sprite.png -o sprite_nobg.png
```

Requires ComfyUI reachable on port 8000 (uploads the image via its HTTP API).
Inspect the result before pixelizing — on a busy/detailed background it may
only be partially transparent rather than clean, in which case re-prompting
is the more reliable fix. Skip this step entirely for Lane C (ChatGPT)
output, which tends to already have a flat background.

### 3. Pixelize

```bash
# Lane A/B (hi-res ComfyUI output): full pipeline
C:\AI-Shared\python.exe scripts\pixelize.py sprite.png --method pixeloe --target-size 64 --colors 32 --alpha

# Lane C (ChatGPT) or any already-pixel-art-styled-but-off-grid input:
C:\AI-Shared\python.exe scripts\pixelize.py sprite.png --method unfake --colors 32 --alpha
```

Skip `--alpha` if you already ran `comfy_rmbg.py` (the image is already
transparent). Full flag reference:

| Flag | Meaning |
|---|---|
| `--method pixeloe\|unfake` | `pixeloe` (default): outline-aware downscale then grid-snap+quantize, for hi-res generations. `unfake`: skip the downscale, for input that's already pixel-art-styled but off-grid. |
| `--target-size N` | Target native grid resolution on the short edge (art pixels). Default 64. Only affects `--method pixeloe`; the actual detected resolution can land coarser — see `references/pixel-prompting.md`. |
| `--colors N` | Max palette size. Default 32. |
| `--palette FILE` | Optional fixed hex-color palette file (one color per line) instead of auto-quantizing. |
| `--alpha` | Flood-fill background transparency during the unfake pass. |
| `--display-size N` | Long edge of the nearest-upscaled `*_final.png` viewing copy. Default 512. |
| `-o / --out-dir` | Default: alongside the input file. |
| `--name` | Output basename. Default: input filename stem. |

Emits `<name>_grid.png` (native resolution — the actual game asset),
`<name>_final.png` (nearest-upscaled for normal viewing), and
`<name>_palette.json`.

### 4. Verify (always — this is not optional)

```bash
venv-unfake\Scripts\python.exe scripts\qc_check.py sprite_grid.png --max-colors 32
```

(Run from this skill's own directory, using its `venv-unfake\Scripts\python.exe`,
not the base interpreter — it needs `unfake`+`numpy`+`PIL`.) Exits 0 on pass, 1 on fail,
and writes `<name>_qc.json`. Read `references/qc.md` for what each of the
four checks means and why a `true_grid` failure specifically usually means
the source needs a different `--method`, not a QC-script bug. **Never hand
back a "pixel art" result without running this — QC failures on real
generations happen** (Phase 0 hit one on ChatGPT output; `pixelize.py`'s
built-in convergence loop handles the common case automatically, but always
confirm with `qc_check.py` rather than assuming it worked).

`qc_check.py` answers "is this a valid pixel grid". It does **not** answer
"is this good art" — it passes sprites that float, have no outline, or whose
walk cycle swaps character halfway through. For that, also run:

```bash
C:\AI-Shared\python.exe scripts\art_qc.py sprite sprite_grid.png
C:\AI-Shared\python.exe scripts\art_qc.py frames f0.png f1.png f2.png f3.png
```

Base interpreter, Pillow only. Checks outline coverage and ground contact on
a single sprite, and silhouette IoU + bbox drift across frames — the
identity-drift detector for multi-frame work. **Feed the `frames` mode
character-isolated art** (transparent except the character) or it scores
background movement instead; see `references/art-qc.md`.

### 5. Present the result

Show the user the `*_final.png` (viewable at normal size) and mention the
native grid resolution and color count from the QC report. If QC failed,
say so plainly and either retry with a different `--method`/`--colors`, or
run RMBG first if it hasn't been tried.

## Lane D — deterministic drawing (no model)

You are the artist; `scripts/pixelstudio.py` is your hand. The
see→critique→fix loop **is** the quality engine — never skip it, and never
show the user a first render.

Requires only Pillow: `C:\AI-Shared\python.exe -c "import PIL"` (verified
present, 10.4.0). No venv, no torch, no ComfyUI.

### The loop

1. **Brief** — canvas size, palette with a **hard color budget**, style,
   outline rule, light direction. Read `references/patterns.md` and
   `references/palettes.md` first, and check
   `references/learned/INDEX.md` for a studied style that matches.
2. **Build script** — create `pixel-art/<slug>/build.py` in the working
   directory. It is the artwork's source of truth and regenerates everything
   on each run. Parametrize shapes (position, squash, frame offset) so
   animation frames are function calls, not copy-paste.

   ```python
   import sys
   sys.path.insert(0, r"C:\Claude\sarges-skills\skills\pixel-art-studio\scripts")
   from pixelstudio import Sprite, PALETTES, ramp, mix

   BODY = ramp("#38b764", 5)                 # hue-shifted 5-step ramp
   s = Sprite(32, 32, palette=BODY + ["#1a1c2c", "#f4f4f4"])

   def draw_slime(squash=0):                 # parametric -> reuse per frame
       s.ellipse(6, 12 + squash, 25, 27, BODY[0])                 # darkest first
       s.ellipse(6, 11 + squash, 24, 26, BODY[2], only="opaque")  # restack toward light
       s.outline(BODY[0], where="inside")                         # selout
   draw_slime()

   s.preview("preview.png", scale=10)        # LOOK at this file
   s.stats()                                 # and READ these numbers
   ```
3. **Run** — `C:\AI-Shared\python.exe build.py` from `pixel-art/<slug>/`.
4. **LOOK** — Read `preview.png` with your own eyes (plus
   `s.save_silhouette()` / `s.zoom()` when unsure). Critique point by point
   against `references/validations.md`, honestly.
5. **Fix** — edit `build.py`, rerun. **Minimum 2–3 passes** before showing
   the user. Check `references/sharp_edges.md` before finalizing.
6. **Deliver** — export the 1x master **and** a 4–8x display copy; GIF or
   spritesheet if animated. Report the 1x path.

Work at true pixel size always. Scale is an export-time concern and **integer
only**.

### API — scripts/pixelstudio.py

Colors: `"#hex"` | `(r,g,b[,a])` | palette index (int) | `None` = erase.
Most ops take `only=` to clip — a color, `"opaque"`, or `"empty"`. That
masking system is what the shifted-shape shading recipe in
`references/techniques.md` is built on.

| Area | Calls |
|---|---|
| Canvas | `Sprite(w, h, palette=None, snap=True)` · `s.layer(name)` · `s.frame(i)` · `s.use(frame=, layer=)` |
| Draw | `px(x,y,c)` `line(x0,y0,x1,y1,c)` `rect(x0,y0,x1,y1,c,fill=True)` `circle(cx,cy,r,c,fill=False)` (pixel-perfect) `ellipse(x0,y0,x1,y1,c,fill=True)` `polygon(points,c)` `contour(points,c)` `fill(x,y,c)` `clear` `get(x,y)` `paste_png` — **color is positional, `fill=` is a bool, not the color** |
| Pixel-art ops | `outline(c, where="outside"/"inside")` · `mirror_x` `mirror_y` · `shift(dx,dy,wrap=)` · `replace(old,new)` · `dither(box,c1,c2,mix,pattern)` · `gradient_dither(box,colors)` · `noise(box,c,density,seed)` |
| Color | `ramp(base, steps, hue_shift)` · `mix(c1,c2,t)` · `PALETTES` · `s.set_palette(p, remap=)` · `s.to_palette(p, dither=)` · `s.quantize(n)` |
| Cleanup | `s.harden_alpha(threshold, steps)` · `s.despeckle(min_cluster)` · `s.dedupe_colors(tol)` · `s.dehalo()` · `s.clean(...)` · `s.before_after(path)` |
| Animation | `s.add_frame(copy=True)` · `s.set_duration(ms, frames)` · `s.tag(name, from, to, direction)` · `s.copy_cel(layer, from_frame, to_frames, link=)` · `s.del_frame` |
| Inspect | `s.preview(path, scale, grid=, labels=)` · `s.zoom(path, x0,y0,x1,y1)` · `s.save_silhouette(path)` · `s.stats()` · `s.save_swatch(path)` · `s.used_colors()` |
| Export | `s.save_png(path, frame, scale, bg)` · `s.save_gif(path, scale, tag, bg)` · `s.save_spritesheet(path, layout, scale, padding)` (+engine JSON) · `s.save_project` / `Sprite.load_project` / `Sprite.from_png(path, scale="auto", strip_bg=)` |

Built-in palettes: `onebit`, `gameboy`, `pico8`, `sweetie16`, `c64`,
`endesga32`.

### LPC universal spritesheet (humanoids)

For a character with 2 arms and 2 legs, `scripts/lpc.py` assembles frames onto
the LPC grid so the result drops into any LPC-aware engine/template. Read
`references/lpc.md`. Only the **grid convention** comes from LPC — no LPC
artwork ships with this skill (see `THIRD-PARTY.md`).

```python
from lpc import LPCSheet, ACTIONS
sheet = LPCSheet()
for action, direction, frame in sheet.slots():   # every cell to fill
    sheet.place(action, direction, frame, draw(action, direction, frame))
sheet.save("hero_lpc.png")                       # + hero_lpc.json meta
sheet.gif("walk_left.gif", "walk", "left", scale=2)
```

**Scope honestly.** The full sheet is 21 rows × 13 cells across six actions
(spellcast 7, thrust 8, walk 9, slash 6, shoot 13, hurt 6). Upstream's own
flagship example fills only walk and slash — 54 of 210 cells — from a 232-line
build script. Filling the whole matrix is a large, expensive job. Agree the
action list with the user up front, and never imply an empty row is done.

### Hybrid — clean a generation into an editable Lane D script

The two lanes compose. Generate the base in A/B/C, then clean it into a
regenerable `build.py` and keep editing deterministically:

```bash
C:\AI-Shared\python.exe scripts\pixelpipe.py gen.png --strip-checker --max-colors 24 --display 6
C:\AI-Shared\python.exe scripts\pixelpipe.py gen.png --palette my_game    # cross-asset lock
```

**`pixelize.py` remains the default for hi-res ComfyUI output** — it has the
PixelOE outline-aware downscale and the QC convergence loop that
`pixelpipe.py` lacks. Use `pixelpipe.py` specifically when you want the
editable `build.py` it emits, or for already-pixel-ish input. Full playbook in
`references/cleanup.md`.

### Learning a style from a reference image

```bash
C:\AI-Shared\python.exe scripts\study.py <file> --save-palette <name>
```

Emits `<file>_study/` with `zoom.png`, `swatch.png`, `silhouette.png`,
`report.json`. Read the zoom and swatch with your own eyes — the report gives
numbers, your eyes extract the *techniques*. Write a card into
`references/learned/NNN-<slug>.md` from `TEMPLATE.md` and add a line to
`references/learned/INDEX.md` **in the same change**. Durable knowledge goes
under the skill directory, never beside the input file.

### Lane D conventions

- Artworks live in `./pixel-art/<slug>/` — `build.py` plus all outputs.
- **Never hand-edit an exported PNG.** It's a compile target; edit `build.py`.
- Randomness only via `noise(seed=)`. Renders must be deterministic.
- Deliver `save_png`/`save_gif`/`save_spritesheet` output only — previews,
  grids, and contact sheets are working documents, not deliverables.

## 8-direction sprite sheets

**Try PixelLab first if `mcp__pixellab__*` tools are available.**
`create_character(mode="standard", n_directions=8)` produces a genuinely
correct 8-direction rotation (proper back view, correctly mirrored side
profiles) for 1 generation — validated 2026-08-14 on the exact "knight, 8
directions" case that fails below on every local lane. Check
`mcp__pixellab__get_balance` first (shared trial account across projects —
don't assume unlimited credits) and see `references/sprite-sheets.md` for
the full comparison. The local ComfyUI path below is the fallback when
PixelLab isn't connected/available, not the first choice for this
specific task.

**If using local generation instead: Lane A (Qwen), not Lane B.**
dreamshaperPixelart_v10 doesn't
understand "reference sheet" composition — three independent attempts
produced a map, a sheet of different character designs, and a crowd scene.
Qwen reliably produces a clean 3x3 grid with a consistent character across
cells. Full findings, including the honest limitation below, in
`references/sprite-sheets.md`.

```bash
# 1. Generate the sheet (Lane A, white background, empty center cell)
C:\AI-Shared\python.exe scripts\comfy_submit_template.py assets\workflows\lane-a-qwen.json --prompt-node 5 --prompt "3x3 grid sprite sheet, plain white background, empty center cell, same character in every outer cell, 8 different facing directions..." --seed-node 8 --seed 300 -o sheet.png

# 2. Pixelize the WHOLE sheet as one unit -- keeps one unified palette/grid
#    across all 8 frames. Scale --target-size up ~3x your usual single-sprite size.
C:\AI-Shared\python.exe scripts\pixelize.py sheet.png --method pixeloe --target-size 192 --colors 32

# 3. Slice into 8 directional frames (NOT browser-game-builder's slice_sprites.py --
#    this skill's own slice_sheet.py, which uses NEAREST not LANCZOS and binarizes
#    alpha, both required to keep true-grid QC passing)
C:\AI-Shared\python.exe scripts\slice_sheet.py sheet_grid.png knight --out assets

# 4. VERIFY FACING -- do not skip. Frame 0 must point right, frame 6 up.
C:\AI-Shared\python.exe scripts\verify_facing.py knight --frames 0-7 --assets assets
# If wrong: re-run slice_sheet.py with --flip (180°) or --mirror (E/W swap)
```

**Honest limitation: direction content, not just composition, is unsolved
locally.** Every generation attempt that got the grid layout right (Lane A)
still rendered the *same front-facing pose in all 8 cells* — no genuine
back/side/rotated views, confirmed across two separate prompt strategies
including an extremely explicit panel-by-panel description. This isn't a
prompting problem to keep iterating on; standard text-to-image models don't
have real pose/3D understanding. Tell the user this plainly rather than
shipping a sheet that only *looks* like it has 8 directions. **PixelLab
(above) is now the validated fix**, not just a recommendation — it's
confirmed to solve exactly this failure mode. If PixelLab isn't available,
the next local lever is `scripts/comfy_edit.py` (Qwen-Edit-2511 pose edits
off a single reference) — see `references/sprite-sheets.md` for the full
comparison.

**Lane D does not solve this either — it changes the question.** LPC is a
**4-direction** convention (up/left/down/right), not 8. It sidesteps rotation
rather than solving it. Drawing by hand does buy you a genuine back view,
which no local generation lane has produced, but be skeptical of the side
views too: in upstream's own flagship character, "left" and "right" are
near-front 3/4 poses with the props mirrored, not true profiles (verified by
cropping the sheet, not from the README). If the user needs a real 8-way
rotation matrix and PixelLab isn't an option, hand-drawing all eight is the
honest fallback — say so instead of shipping mirrored 3/4s labelled as
directions.

## Walk/idle animation

**PixelLab's `animate_character` is validated for this** (2026-08-14):
`template_animation_id="walk"` across all 8 directions in one call produced
a genuinely smooth 6-frame walk cycle per direction — clear leg/arm
articulation, consistent identity, every frame QC-passing, no pixelize.py
step needed. It covers all 8 directions at once; see the dozens of other
`available_animations` template names (run, jump, attack, death, etc.) on
`get_character`'s output for non-walk needs.

If PixelLab isn't available, **single-pose edits via `scripts/comfy_edit.py`
(Qwen-Edit-2511) are the local fallback and genuinely work** for a one-off
pose: two independent edit passes against the same reference image ("left
leg forward" / "right leg forward") produced a real alternating stride, both
frames QC-passing, identity preserved. This conditions on an actual
reference image rather than blind multi-panel text generation, which is why
it succeeds where the direction-sheet approach doesn't — but it's one
direction and one pose pair per invocation, not the full matrix PixelLab
covers in one call. Budget the first edit pass's ~22 min cold load, then
expect faster subsequent passes. See `references/sprite-sheets.md` for the
full comparison and when to reach for which.

Measure drift rather than eyeballing it — `art_qc.py frames` reports
silhouette IoU and bbox drift, which is what "identity preserved" actually
means. Generate the frames on a transparent background, though: the existing
`eval-3-walk` frames kept their backdrop and VFX, so the metric scores the
scenery moving rather than the character. See `references/art-qc.md`.

## Tilesets

A tile is not a sprite: it has to survive being laid next to a copy of
itself. **Generate at 3x the tile size and keep the center crop** — a framed
image cannot be made to tile without wrecking its edges, and every fix below
is damage control for skipping this.

```bash
# score, then fix (writes *_seamless.png + *_seam.json)
C:\AI-Shared\python.exe scripts\tileset.py seam grass.png
C:\AI-Shared\python.exe scripts\tileset.py fix grass_96.png --crop-center 32

# score every tile in a packed sheet — names the worst offender
C:\AI-Shared\python.exe scripts\tileset.py sheet overworld.png --tile-size 32 --columns 8

# emit Tiled TSX + a demo TMJ map
C:\AI-Shared\python.exe scripts\tileset.py export overworld.png --tile-size 32 \
    --columns 8 --names grass,dirt,water,stone
```

`--strategy auto` escalates torus → edge_match and keeps whichever scores
best, never returning something worse than the input. **Always look at
`edge_match` output**: it passes the gate by construction because it forces
the edges equal, so the score says nothing about whether it still looks
right. `references/tilesets.md` has a montage snippet for checking.

Tiled TSX is a *tileset* definition — distinct from the Aseprite/Unity/Godot
*spritesheet* formats in `references/export.md`, which are for animation
frames. Wilmington 16-Bit and skill-snes-rpg both consume TSX.

## Worked example: an asset request for a game project

A concrete pattern, using Bounty Hunter X (a `snes-action-platformer`-built
Godot 4 Mega Man X-style game) as the example — the same shape applies to
any consumer project that specs sprites via that skill's
`assets/spritesheet-spec.md`:

> "I need a new enemy sprite for Bounty Hunter X — a small hovering drone
> turret, idle + a 2-frame fire animation, matching the fodder-enemy spec
> (16×16, ~15 colors)."

1. Read the consuming skill's own spec first (here,
   `snes-action-platformer/assets/spritesheet-spec.md`'s Enemy sizes table
   and Palette guidance) — don't guess resolution/color-budget/facing
   conventions, they're already decided per-project.
2. Generate via Lane B (`comfy_submit.py`, single sprite — this is a static
   pose request, not a sheet) with the project's exact vocabulary: "pixel
   art hovering drone turret, small fodder enemy, 16-bit style, flat colors,
   no anti-aliasing, solid single-color background, game asset."
3. `pixelize.py --target-size 16 --colors 15 --alpha` (spec's numbers, not
   this skill's own 64/32 defaults).
4. For the fire-animation second frame: `comfy_edit.py` against the idle
   generation, instruction "the turret's barrel glowing and extended,
   mid-fire, same turret, same colors, same background" — the proven
   single-pose-edit lever, not a multi-panel sheet attempt.
5. `qc_check.py` both frames; only then hand them back to the
   `snes-action-platformer` session to slot into its `AnimatedSprite2D`
   setup per the spec's export conventions (feet-center origin, right-facing
   only, single sheet per entity).

## Knowledge routing

| Task | Read |
|---|---|
| Writing the generation prompt (Lanes A/B/C) | `references/pixel-prompting.md` |
| What the QC checks mean and how to fix a failure | `references/qc.md` |
| Art-quality + frame-drift metrics (the other half of QC) | `references/art-qc.md` |
| Seamless tiles, seam scoring, Tiled TSX/TMJ export | `references/tilesets.md` |
| Sheet generation findings, Qwen-Edit results, PixelLab buy-gate | `references/sprite-sheets.md` |
| **Lane D:** sizes, chibi/heroic/tall proportions, silhouette-first order, tiles | `references/patterns.md` |
| **Lane D:** ramps, shading, dithering, AA, outlines, textures | `references/techniques.md` |
| **Lane D:** frame counts, timing, puppeting, stable pivots | `references/animation.md` |
| **Lane D:** LPC sheet assembly for humanoids | `references/lpc.md` + `scripts/lpc.py` |
| **Lane D:** palette choice, budgets, presets, learned palettes | `references/palettes.md` |
| **Lane D:** engine export formats (Unity/Godot/Phaser) | `references/export.md` |
| Hybrid — cleaning generated art into an editable build.py | `references/cleanup.md` |
| **Known failure modes — read before finalizing any Lane D art** | `references/sharp_edges.md` |
| Per-iteration critique checklist | `references/validations.md` |
| Studied styles from reference art | `references/learned/INDEX.md` |

## Handoffs

- ComfyUI submission plumbing, model routing, VRAM/recovery management,
  prompt-expansion patterns → `comfyui-studio` (this skill only owns the
  pixel-specific templates and the post-process pipeline)
- ChatGPT desktop automation (Lane C) → `chatgpt-desktop`
- Sprite sheet slicing + facing verification (once Phase 2 is built) →
  `browser-game-builder`'s `slice_sprites.py` / `verify_facing.py`
- Lane D engine provenance and license → `THIRD-PARTY.md`
  (MIT, github.com/Gamezxz/pixel-art-studio)
