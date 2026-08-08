# Art QC — is it good art, not just a valid grid

`scripts/art_qc.py`. Pure Pillow, base interpreter (`C:\AI-Shared\python.exe`).

## Two QC scripts, neither replaces the other

| Script | Answers | Interpreter |
|---|---|---|
| `qc_check.py` | is this a valid **pixel grid**? true-grid resolution, color count, binary alpha, exact integer upscale | `venv-unfake` |
| `art_qc.py` | is this good **art**? outline, ground contact, and frame-to-frame consistency | base |

`qc_check.py` will happily pass a sprite that floats, has no outline, and
whose walk cycle swaps character halfway through. Run both.

## Frame consistency — the reason this exists

`references/sprite-sheets.md` ends on an open question: whether a 3rd or 4th
Qwen-Edit frame holds identity, "untested… whether identity drift creeps in
over more edit passes." Until now the only way to check was by eye.

```bash
python scripts/art_qc.py frames f0.png f1.png f2.png f3.png
python scripts/art_qc.py sheet walk.png --tile-size 32 --frames 4
```

| Metric | Gate | Means |
|---|---|---|
| `silhouette_iou` | ≥ 0.85 hard | overlap of frame 0's silhouette with the frame half a cycle away. **The identity-drift detector** — same character in a different pose still overlaps heavily; a quietly redrawn character does not |
| `bbox_drift_x` | ≤ 6 hard | horizontal spread. Loose on purpose — a contact pose is legitimately several px wider than a passing pose. Catches size changes, not pose changes |
| `bbox_drift_y` | ≤ 3 hard | vertical drift. Tight — `animation.md` says the bob is exactly 1 px. More than 3 means the character is sinking or rising, i.e. floating feet |
| `alpha_crispness` | ≥ 0.999 hard | worst frame's share of alpha values that are exactly 0 or 255 |

Frames must be the same size — normalize first (`slice_sheet.py` does).

### Validated against controls

A hand-built 4-frame cycle (consistent character, 1 px bob) scores
**IoU 1.000, y-drift 1 — PASS**. The same cycle with frame 2 recolored and
sunk 5 px scores **IoU 0.577, y-drift 5 — HARD-FAIL**. The metrics detect
what they claim to.

### The precondition — read this before believing a FAIL

**Feed it character-isolated frames.** Transparent everywhere except the
character. If frames still carry a background, VFX or scenery, those pixels
are part of the silhouette and their movement is what gets scored.

`opaque_fraction` catches the blunt version (a fully-opaque frame has no
silhouette at all) and demotes the frame gates to info when it fires. It does
**not** catch the subtle version, and the subtle version is the common one:

> This skill's own `evals/eval-3-walk` pair measures 0.68 opaque — it passes
> the check — and still scores IoU 0.70, the same range as the sabotaged
> control. An overlay shows why: those frames kept the grey backdrop blob,
> the red VFX arc and the grass. The silhouette is a whole *scene*, and what
> moved between frames is scenery.

So that pair is **not evidence the Qwen-Edit stride result was wrong** — it
is evidence the frames are the wrong input for this measurement. Re-generate
on a transparent background before drawing any conclusion about drift. No
cheap metric separates character pixels from scenery pixels, so none here
tries to.

## Single-sprite metrics

```bash
python scripts/art_qc.py sprite knight_grid.png
```

| Metric | Gate | Means |
|---|---|---|
| `outline_coverage` | ≥ 0.85 **soft** | share of silhouette-edge pixels in the darkest quartile of the sprite's own colors. High = a deliberate dark outline ring |
| `baseline_alignment` | ≥ 3 contiguous, hard | the lowest opaque row must have real width. A sprite ending in one stray pixel has no ground contact and will not sit on a tile floor |
| `alpha_crispness` | ≥ 0.999 hard | share of alpha values exactly 0 or 255 |
| `palette_size` | info | distinct opaque colors |

`outline_coverage` is **soft** because outline-free styles are legitimate. It
discriminates well: the outlined control sprite scores 1.000, the
un-outlined `eval-1` knight scores 0.108. A low score is a question, not a
verdict.

`palette_fidelity` from upstream is deliberately **not implemented**. It
hard-fails anything not 100% on a named palette, which is only meaningful if
you force-quantize to one — meaningless against unfake's adaptive per-image
palettes.

## Threshold honesty

Every number in `GATES` is upstream's starting value, calibrated against
upstream's art, on a repo with 6 stars and no external validation. They were
sanity-checked here against controls and against this skill's real evals, and
they behaved — but re-tune against your own known-good output before treating
a FAIL as authoritative.
