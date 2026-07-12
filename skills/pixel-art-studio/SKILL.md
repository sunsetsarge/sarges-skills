---
name: pixel-art-studio
description: Generate game-usable, true-grid pixel art (character sprites, tiles, icons) using the local ComfyUI install, with a Python post-process pipeline that turns any AI generation into authentic low-color pixel art -- verified programmatically, not eyeballed. Use this whenever the user asks for pixel art, a sprite, a tileset, an 8-bit or 16-bit game asset, a spritesheet frame, or retro/SNES-style game art, even if they don't name a tool or resolution. Also use it to clean up an existing "pixel-art-ish" image (e.g. from ChatGPT/DALL-E) into a true grid. NOT for photorealistic or non-pixel-style image generation (comfyui-studio), and NOT yet for multi-frame animation or 8-direction sheets (that's a planned Phase 2 -- say so rather than attempting it).
---

# Pixel Art Studio

Produces true-grid pixel art PNGs: generate with the local ComfyUI install (or
ChatGPT desktop, named explicitly), then run every result through a Python
post-process pipeline that grid-snaps, quantizes, and verifies the output --
so "pixel art" means an actual low-resolution color-quantized grid, not an
AI image that merely looks blocky at a glance.

**Division of labor:** ComfyUI only generates. `scripts/pixelize.py` (this
skill) owns 100% of the pixelization — no ComfyUI custom node does grid-snap
or quantization here. This is deliberate: ComfyUI-Manager blocks node
installs on this machine, and doing pixelization in Python makes the same
pipeline work identically on ComfyUI output, ChatGPT output, or any existing
image on disk.

## The three lanes

| Lane | Model | When to use | License |
|---|---|---|---|
| **B (default for single sprites)** | `dreamshaperPixelart_v10.safetensors` (SD1.5, 512px) | Best authentic pixel-art texture, least post-processing needed | OpenRAIL — check terms before commercial use |
| **A** | Qwen-Image (via Lightning LoRA, ~1328px) | Complex scenes, stronger prompt adherence, commercial-safe | Apache-2.0 |
| **C** | ChatGPT desktop / DALL-E | **Only when the user explicitly names ChatGPT** (per `chatgpt-desktop`'s own trigger rule) — strongest stylistic quality, always off-grid | Follows OpenAI's terms |

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

### 5. Present the result

Show the user the `*_final.png` (viewable at normal size) and mention the
native grid resolution and color count from the QC report. If QC failed,
say so plainly and either retry with a different `--method`/`--colors`, or
run RMBG first if it hasn't been tried.

## What this skill does NOT do yet

Multi-frame sheets (8-direction character sheets, walk cycles) are a planned
Phase 2, not built. If asked for a spritesheet or animation, say that's not
implemented yet rather than attempting an ad-hoc version — the intended path
reuses `browser-game-builder`'s `slice_sprites.py` / `verify_facing.py` plus
a PixelLab.ai API buy-option for skeleton animation (Blaine-gated), per
`Projects\PixelArt_Studio\PLAN.md` Phase 2.

## Handoffs

- ComfyUI submission plumbing, model routing, VRAM/recovery management,
  prompt-expansion patterns → `comfyui-studio` (this skill only owns the
  pixel-specific templates and the post-process pipeline)
- ChatGPT desktop automation (Lane C) → `chatgpt-desktop`
- Sprite sheet slicing + facing verification (once Phase 2 is built) →
  `browser-game-builder`'s `slice_sprites.py` / `verify_facing.py`
