"""Scripted QC for pixelize.py output. Not eyeballed -- every check is
programmatic:

  1. true-grid: re-analyzing the *_grid.png (native resolution, pre-upscale)
     with unfake's own scale detectors must find scale == 1 -- i.e. the grid
     image is already at its native pixel-art resolution, no further
     downscaling possible.
  2. color count on the grid image <= max-colors (default 32).
  3. clean alpha: if the grid image has an alpha channel, every pixel's alpha
     must be binary (0 or 255) -- no soft/anti-aliased edges.
  4. crisp at 400% zoom: the *_final.png must be an exact integer nearest-
     neighbor upscale of *_grid.png -- every scale x scale block in the final
     image is a single solid color matching the grid pixel. This is what
     "crisp at 400% zoom" means, verified instead of eyeballed.

Runs under the venv-unfake interpreter (needs unfake + numpy + PIL).
Usage: venv-unfake/Scripts/python.exe qc_check.py <grid.png> [--final final.png] [--max-colors 32]
If --final is omitted, it's inferred by replacing "_grid.png" with "_final.png".
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import unfake
from PIL import Image


def check_true_grid(grid_arr: np.ndarray) -> dict:
    """runs_based_detect is the authoritative signal: empirically (this skill's
    own acceptance test) edge_aware_detect can false-positive a large scale on
    a genuinely-correct true-grid image when a big uniform-color region (e.g. a
    flat background dominating the frame) fools its block-pattern search --
    confirmed by re-running edge_aware_detect on a known-good, manually-verified
    65x65 sprite and getting a false "18" while runs_based_detect correctly
    returned 1. So: pass on runs_based_detect == 1 alone; edge_aware_detect is
    still reported for transparency and flagged as a note when it disagrees,
    but doesn't gate the result."""
    runs_scale = unfake.runs_based_detect(grid_arr)
    edge_scale = unfake.edge_aware_detect(grid_arr)
    result = {
        "runs_based_scale": int(runs_scale),
        "edge_aware_scale": int(edge_scale),
        "pass": runs_scale == 1,
    }
    if runs_scale == 1 and edge_scale != 1:
        result["note"] = ("edge_aware_detect disagreed (see references/qc.md) -- "
                           "treated as a known false-positive, not a failure")
    return result


def check_color_count(grid_arr: np.ndarray, max_colors: int) -> dict:
    count = unfake.count_colors(grid_arr)
    return {"count": int(count), "max_allowed": max_colors, "pass": count <= max_colors}


def check_alpha_clean(grid_arr: np.ndarray) -> dict:
    if grid_arr.shape[2] < 4:
        return {"has_alpha": False, "pass": True, "note": "no alpha channel (opaque image)"}
    alpha = grid_arr[:, :, 3]
    unique_vals = np.unique(alpha)
    binary = bool(np.all((unique_vals == 0) | (unique_vals == 255)))
    return {
        "has_alpha": True,
        "unique_alpha_values": [int(v) for v in unique_vals[:20]],
        "pass": binary,
    }


def check_crisp_upscale(grid_img: Image.Image, final_img: Image.Image) -> dict:
    gw, gh = grid_img.size
    fw, fh = final_img.size
    if gw == 0 or gh == 0 or fw % gw != 0 or fh % gh != 0:
        return {"pass": False, "note": "final size is not an integer multiple of grid size"}
    sx, sy = fw // gw, fh // gh
    if sx != sy:
        return {"pass": False, "note": f"non-uniform scale factors sx={sx} sy={sy}"}

    final_arr = np.array(final_img.convert("RGBA"))
    grid_arr = np.array(grid_img.convert("RGBA"))
    blocks = final_arr.reshape(gh, sy, gw, sx, 4)
    block_uniform = np.all(blocks == blocks[:, :1, :, :1, :], axis=(1, 3))
    all_uniform = bool(np.all(block_uniform))
    matches_grid = bool(np.array_equal(blocks[:, 0, :, 0], grid_arr))
    return {
        "scale_factor": int(sx),
        "all_blocks_uniform": all_uniform,
        "matches_grid_pixels": matches_grid,
        "pass": all_uniform and matches_grid,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("grid", help="Path to a *_grid.png produced by pixelize.py")
    ap.add_argument("--final", help="Path to the matching *_final.png "
                                     "(default: infer by replacing _grid.png -> _final.png)")
    ap.add_argument("--max-colors", type=int, default=32)
    args = ap.parse_args()

    grid_path = Path(args.grid).resolve()
    final_path = Path(args.final).resolve() if args.final else \
        grid_path.with_name(grid_path.name.replace("_grid.png", "_final.png"))

    if not grid_path.exists() or not final_path.exists():
        print(f"FAIL: missing grid or final PNG (grid={grid_path}, final={final_path})",
              file=sys.stderr)
        sys.exit(2)

    grid_img = Image.open(grid_path).convert("RGBA")
    final_img = Image.open(final_path).convert("RGBA")
    grid_arr = np.array(grid_img)

    report = {
        "grid_file": str(grid_path),
        "final_file": str(final_path),
        "grid_size": list(grid_img.size),
        "final_size": list(final_img.size),
        "true_grid": check_true_grid(grid_arr),
        "color_count": check_color_count(grid_arr, args.max_colors),
        "alpha_clean": check_alpha_clean(grid_arr),
        "crisp_upscale": check_crisp_upscale(grid_img, final_img),
    }
    report["pass"] = all(report[k]["pass"] for k in
                          ("true_grid", "color_count", "alpha_clean", "crisp_upscale"))

    report_path = grid_path.with_name(grid_path.stem.replace("_grid", "") + "_qc.json")
    report_path.write_text(json.dumps(report, indent=2))

    status = "PASS" if report["pass"] else "FAIL"
    print(f"{status}: {grid_path.name}")
    for key in ("true_grid", "color_count", "alpha_clean", "crisp_upscale"):
        sub = report[key]
        print(f"  {key}: {'pass' if sub['pass'] else 'FAIL'} -- {sub}")

    sys.exit(0 if report["pass"] else 1)


if __name__ == "__main__":
    main()
