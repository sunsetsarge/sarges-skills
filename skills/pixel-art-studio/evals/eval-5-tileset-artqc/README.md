# eval-5 — tileset.py + art_qc.py validation (2026-08-08)

Evidence that the two scripts ported from
ianlintner/ai-pixel-art-image-generation do what they claim. All artifacts
built with Lane D (`pixelstudio.py`) so they are reproducible without
ComfyUI. 14/14 regression checks passed, including exit codes.

## Seam scoring and repair

| File | seam_diff | Note |
|---|---|---|
| `grass_bad.png` | **93.704** | deliberate left-dark→right-light ramp; cannot tile |
| `grass_good.png` | **9.827** | wrapped noise on a flat base; tiles fine, left untouched by `fix` |
| `grass_bad_seamless.png` | **0.000** | after `fix --strategy auto` |

`grass_bad_seamless_seam.json` records the escalation: `none` 93.704 →
`torus` 61.470 → `edge_match` 0.000. **torus was not enough**, which is the
normal case — the polite strategy usually loses.

`compare.png` is the proof that matters: 3×3 montages of `grass_bad` (left)
and the repaired tile (right). The left shows a hard vertical seam repeating
every 32 px; the right is continuous. The score dropping is not evidence on
its own — `edge_match` passes the gate *by construction*, so it always needs
an eyeball check.

## Tiled export

`overworld.png` (128×32, 4 tiles) → `overworld.tsx` + `overworld.tmj`.
Verified by parsing rather than by inspection: TSX root attributes, image
dims, per-tile `name` properties, a 2-frame animation block on tile 0; TMJ
layer length equal to width×height and all cells `1` (firstgid-offset — `0`
would mean empty). Grid-dim mismatch exits 2 with a clean message.

`sheet` mode over the same image correctly isolated tile 2 (the unrepaired
`grass_bad`) as the worst at 93.704 while the other three passed.

## Frame-consistency controls

Hand-built 4-frame walk cycles, character-isolated on transparency.

| Set | silhouette_iou | bbox_drift_y | Result |
|---|---|---|---|
| `control_good_*` — consistent character, 1 px bob | **1.000** | 1 | PASS |
| `control_bad_*` — frame 2 recolored + sunk 5 px | **0.577** | 5 | HARD-FAIL |

The metrics detect exactly the failure they claim to.

`outline_coverage` discriminates too: **1.000** on the outlined control vs
**0.108** on the real un-outlined `eval-1` knight. Soft-gated, because
outline-free styles are legitimate.

## The precondition finding

`walk_overlay.png` — `eval-3-walk` frames A and B, then an overlay (red =
A only, blue = B only, purple = both).

That pair scores IoU 0.70 and 4 px of y-drift, the same range as the
*sabotaged* control. The overlay shows why, and it is **not** character
drift: the frames kept the grey backdrop blob, the red VFX arc and the
grass, so the alpha silhouette is a whole scene and what moved is scenery.
The character itself is stable.

`opaque_fraction` measures 0.68 there — below the 0.90 guard, so the guard
does not fire. It catches only the blunt case (a fully-opaque frame has no
silhouette at all). No cheap metric separates character pixels from scenery
pixels, so none is attempted.

**Consequence: this does not refute `sprite-sheets.md`'s positive Qwen-Edit
stride result.** It shows those frames are the wrong input for the
measurement. Re-generate on a transparent background before concluding
anything about multi-frame drift — which remains the open question it always
was.
