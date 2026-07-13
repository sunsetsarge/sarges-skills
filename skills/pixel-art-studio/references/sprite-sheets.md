# Sprite sheets (Phase 2)

## What works: composition and per-cell slicing

The pipeline for turning one generated image into 8 directional frames is
proven and reliable:

1. **Generate a 3x3 sheet** on a plain white background, empty center cell,
   with the outer 8 cells arranged as compass directions (top row NW/N/NE,
   middle row W/empty/E, bottom row SW/S/SE — the same convention
   browser-game-builder uses). **Lane A (Qwen) reliably nails the
   composition and character consistency** — clean grid lines, correctly
   empty center, same armor/colors/proportions in every cell. Lane B
   (dreamshaperPixelart_v10) does not: three independent attempts produced a
   top-down village map, a sheet of ~18 *different* knight designs, and a
   crowd scene — it doesn't understand "reference sheet" composition and
   "grid"/"tile" language pulls it toward environment art. **Use Lane A for
   sheets; Lane B is still fine for single sprites** (see
   `pixel-prompting.md`).
2. **Pixelize the whole sheet as one image**, not per-cell — this keeps a
   single unified palette and native grid resolution across all 8 frames
   (`pixelize.py --method pixeloe --target-size <3x your usual single-sprite
   target>`, e.g. 192 for a normal 64px sprite). Slicing after quantizing a
   full-color sheet per-cell would risk each frame landing on a slightly
   different palette.
3. **Slice with `scripts/slice_sheet.py`** (adapted from
   browser-game-builder's `slice_sprites.py`): white-key removal, cut into 9
   cells, map the 8 outer cells to compass frames, trim each to content,
   normalize to a common size with **integer NEAREST scaling only** — the
   original script uses LANCZOS, which is correct for normal sprite art but
   destroys true-grid pixel art (soft, anti-aliased scaling breaks every QC
   check). Also binarizes alpha after the white-key (the original's soft key
   left partial alpha values, e.g. 4/60/139/255 instead of 0/255 — confirmed
   directly on this skill's own test output).
4. **Verify with `scripts/verify_facing.py`** (copied verbatim from
   browser-game-builder — it only montages PNGs, nothing pixel-art-specific
   to change). Frame 0 must point right, frame 6 up; use `--flip`/`--mirror`
   on the slicer if not.
5. **QC each frame** the same way as any pixelize.py output — slicing
   preserves true-grid/color-count/alpha-clean/crisp-upscale as long as you
   used the fixes above (NEAREST + alpha binarization).

## What doesn't work yet: actual directional rotation

**Five independent generation attempts across both local lanes** (three on
Lane B with progressively different prompt strategies — grid/tile language,
turnaround-sheet language, rotation-around-Y-axis language; two on Lane A,
including one with an extremely explicit panel-by-panel description of what
each of the 8 cells should show) all produced the **same front-facing pose
repeated in every cell**, sometimes with a random minor prop change (a
shield appearing in 3 of 9 panels) but never an actual back view, side
profile, or 3/4 angle. This wasn't a fluke of one bad prompt — every attempt
that got the *composition* right (Lane A, both tries) failed identically at
*content* variation by direction.

**Why:** standard text-to-image diffusion models have no real 3D/pose
understanding. They can learn "put N copies of X in a grid" as a
composition pattern (that's a 2D layout task) but "show X rotated 45° per
panel" requires actual spatial reasoning about the subject's geometry that
these models don't have. This matches what PLAN.md's original research
flagged as the likely outcome ("the research says ComfyUI is still clumsy
here") — it's not a prompting skill issue, it's a capability gap.

**What this means practically:** for a genuine 8-direction character sheet,
budget for one of:
- **Manual per-direction generation + Qwen-Edit-2511 pose edits** off a
  single canonical reference (see `scripts/comfy_edit.py`) — untested at
  scale as of this writing (Phase 2's honest walk-cycle attempt used this
  lever; see below for the result), but conditions on actual image structure
  rather than blind multi-panel text generation, so it's the more promising
  local lever if you need to keep pushing on this.
- **ControlNet pose conditioning** on Lane B/SDXL (comfyui-studio has
  `controlnet-union-sdxl-promax.safetensors` installed) — not attempted in
  Phase 2, would need a reference pose skeleton per direction.
- **PixelLab.ai's API** ($12/mo tier, ≤320×320 + skeleton animation,
  commercial license included) — the buy-option PLAN.md flagged from the
  start. Given five failed local attempts, **this is the pragmatic
  recommendation** for production 8-direction sheets rather than continuing
  to fight local generation — Blaine gate (B1 in PLAN.md).

## Walk/idle cycle attempt — a real positive result

Unlike blind multi-panel generation, **Qwen-Edit-2511 pose edits off a
single reference image worked.** Method (`scripts/comfy_edit.py`): take one
existing single-character generation, submit two separate edit passes
against the *same original* (not chained — editing frame A to make frame B
would compound drift), each asking for an alternating stride: "left leg
forward and bent, right leg back and straight, opposite arm forward" for
frame A, the mirrored instruction for frame B.

Result: both frames preserved character identity (hair, outfit, colors,
background, even an unrelated red VFX streak from the source image) while
genuinely varying the pose — different leg forward, different arm forward,
a real alternating stride when viewed side by side. Both passed every QC
check after pixelizing (`pixelize.py --target-size 64 --colors 32 --alpha`,
same settings as a normal single sprite) — true-grid, ≤32 colors, clean
binary alpha, verified crisp upscale. Evidence at
`evals/eval-3-walk/` (walk_frame_a/b raw + pixelized + QC JSON).

**Caveats before calling this solved:**
- Only tested 2 frames (one full stride cycle needs 2-4 for a clean loop —
  untested whether a 3rd/4th intermediate frame stays as consistent, or
  whether identity drift creeps in over more edit passes).
- First cold load of this template is genuinely slow (~22 min, matches
  comfyui-studio's own documented number) — budget for that on a fresh
  ComfyUI session; subsequent edits in the same session are much faster.
- This is a walk *stride* test (legs/arms), not a full 8-direction ×
  N-frame animation matrix — extending this to all 8 facings would be 8×
  the edit passes, with no evidence yet on whether identity holds that far
  or whether editing quality degrades directionally (e.g. editing a
  side-view differently than a front-view).
- Doesn't replace the sheet-generation gap above — this is a per-character,
  per-pose-pair workflow, not a one-shot multi-direction sheet.

**Verdict:** promising enough to be the recommended next lever if pushing
further on local animation (rather than jumping straight to PixelLab), but
not yet a turnkey walk-cycle pipeline. For production 8-direction ×
multi-frame work, PixelLab.ai's skeleton animation is still the more
reliable bet per PLAN.md's original buy-gate — this finding narrows *when*
to reach for it (single-pose edits: try Qwen-Edit first; full direction ×
animation matrices: PixelLab is probably worth the $12/mo up front).
