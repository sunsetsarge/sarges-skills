# Pixel art prompting — per-lane notes

Findings below come from Phase 0's real generations (one sprite per lane, then run
through the full pipeline and QC), not from general knowledge about these models —
trust this over intuition when they conflict.

## Resolutions

- **Lane B (dreamshaperPixelart_v10, SD1.5):** native 512×512. This is a checkpoint
  actually fine-tuned on pixel art, so it needs the least help — Phase 0's output
  converged to true-grid in a single pixelize.py pass with no extra unfake iterations.
- **Lane A (Qwen-Image):** native ~1328×1328 (see comfyui-studio's decision table).
  Qwen isn't pixel-art-tuned — it renders a "pixel art style" illustration, not an
  authentic low-res grid. `pixelize.py --target-size 64` still works, but the actual
  detected native resolution often lands much coarser than the target (Phase 0: a
  1328px image with `--target-size 64` converged to a 22×22 grid, not 64×64) because
  unfake's scale detector finds the *real* underlying block pattern, which is chunkier
  and less consistent than a purpose-built pixel-art model produces. If you need a
  specific resolution, expect to iterate the target-size argument, or prefer Lane B
  when resolution precision matters more than Qwen's stronger prompt adherence.
- **Lane C (ChatGPT/DALL-E):** whatever ChatGPT returns (Phase 0: 1122×1402). Always
  off-grid — use `--method unfake` and let unfake's auto-detect handle the downscale;
  do not run pixeloe on ChatGPT output (it's already been through DALL-E's own
  stylization, pixeloe's contrast-downscale adds nothing and can distort proportions).

## "No anti-aliasing / flat shading" prompt patterns

All three lanes respond to the same core vocabulary — layer these in order of impact:

1. **Style anchor:** "pixel art", "16-bit" / "8-bit", "SNES RPG sprite style" /
   "retro game asset". Name a console era — it's a stronger signal than "pixel art"
   alone.
2. **Anti-aliasing suppression:** "no anti-aliasing", "flat colors", "crisp pixel
   grid", "hard edges". Put this in the negative prompt too when the model supports
   one (Lane A/B): "blurry, anti-aliased, smooth gradient, soft shading, jpeg
   artifacts, photorealistic, 3d render".
3. **Pose/framing:** "front facing, standing pose, full body" for a base character
   sprite. Add "T-pose" only if you're about to rig/animate — it reads badly as a
   standalone sprite.
4. **Background:** see below — this is the weakest link across all three lanes.

## Background prompting — the real gap

**"Simple background" is not enough.** Phase 0 asked for "simple background" on both
Lane A and Lane B and got full scenic renders anyway (Lane B: trees + a house; Lane A:
a textured off-white studio backdrop) — good enough for `--alpha`'s edge flood-fill to
partially clear on Lane A, but Lane B's background survived mostly intact because the
scene touched all four edges with varying colors, so the flood-fill had no clean edge
color to key off. Lane C (ChatGPT) was the one lane that respected "simple background"
and produced a flood-fill-friendly flat backdrop.

Two ways to handle this, in order of preference:

1. **Prompt harder.** Use "solid single-color background, no scenery, studio
   background" instead of "simple background" — this is what the shipped Lane A/B
   workflow templates (`assets/workflows/lane-a-qwen.json`,
   `lane-b-dreamshaper.json`) use by default. Still not guaranteed on Lane A/B.
2. **Run RMBG instead of flood-fill.** For anything with a scenic/complex background,
   run `scripts/comfy_rmbg.py` (background removal via the installed ComfyUI-RMBG
   custom node, INSPYRENET model) on the raw generation *before* `pixelize.py`, and
   skip `--alpha` in the pixelize step (the image is already transparent). This is
   the reliable path — don't burn retries on prompt-only background control for
   Lane A/B.

## Per-lane strengths (pick by what you need)

| Need | Lane |
|---|---|
| Best authentic pixel-art texture, least post-processing needed | B (dreamshaperPixelart_v10) |
| Strongest prompt adherence / complex scenes, commercial-safe (Apache) | A (Qwen) — but budget for a heavier pixelize pass and expect coarser resolution than requested |
| Best stylistic quality of the three, but always off-grid and GUI-automation-fragile | C (ChatGPT) — only when Blaine names ChatGPT explicitly, per chatgpt-desktop's own trigger rule |
| Clean transparent background without fighting the prompt | Any lane + `comfy_rmbg.py`, skip `--alpha` |

## Commercial-use license reminder

Lane A (Qwen) is Apache-2.0 — safe for sold products. Lane B
(dreamshaperPixelart_v10) is OpenRAIL — check the license terms before using output
in anything sold, same guardrail comfyui-studio applies to its own SDXL/OpenRAIL
rows. Lane C (ChatGPT/DALL-E) output licensing follows OpenAI's terms, not this
skill's call to make.
