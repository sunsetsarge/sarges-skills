"""pixel-art-studio's core: turn any raw generated image into game-usable
true-grid pixel art. Runs under the base interpreter (C:\\AI-Shared\\python.exe
-- only needs Pillow, which is already present there). Shells out to two
isolated venvs so neither disturbs the production ComfyUI environment:

  venv-pixeloe  -- outline-aware contrast downscale (pixeloe_worker.py)
  venv-unfake   -- scale auto-detect, grid snap, Wu color quantization,
                   optional background transparency (unfake CLI)

Pipeline (--method pixeloe, the default -- use for hi-res ComfyUI output):
  raw PNG -> pixeloe outline-aware downscale -> unfake grid-snap + quantize
           -> nearest-neighbor upscale to a display size

Pipeline (--method unfake -- use for input that's already pixel-art-styled
but off-grid, e.g. ChatGPT/DALL-E output; unfake's own auto-detect handles
the downscale):
  raw PNG -> unfake grid-snap + quantize -> nearest-neighbor upscale

A single unfake pass doesn't always fully converge to a true grid -- see
converge_grid() below, which iterates until both of unfake's scale detectors
agree the result is already at native resolution (this is what qc_check.py
verifies downstream).

Emits, per input:
  <name>_grid.png   (native true-grid resolution -- the QC target)
  <name>_final.png  (nearest-upscaled for normal viewing)
  <name>_palette.json
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image

SKILL_DIR = Path(__file__).resolve().parent.parent
VENV_PIXELOE_PY = SKILL_DIR / "venv-pixeloe" / "Scripts" / "python.exe"
VENV_UNFAKE_PY = SKILL_DIR / "venv-unfake" / "Scripts" / "python.exe"
VENV_UNFAKE_CLI = SKILL_DIR / "venv-unfake" / "Scripts" / "unfake.exe"
PIXELOE_WORKER = Path(__file__).resolve().parent / "pixeloe_worker.py"


def run_pixeloe(input_path: Path, out_path: Path, target_size: int) -> None:
    cmd = [str(VENV_PIXELOE_PY), str(PIXELOE_WORKER), str(input_path), str(out_path),
           "--target-size", str(target_size)]
    subprocess.run(cmd, check=True)


def run_unfake(input_path: Path, out_path: Path, colors: int, alpha: bool,
               palette: Path | None, manual_scale: int | None = None) -> None:
    cmd = [str(VENV_UNFAKE_CLI), str(input_path), "-o", str(out_path),
           "-c", str(colors), "--cleanup", "morph,jaggy"]
    if alpha:
        cmd.append("--transparent-background")
    if palette:
        cmd += ["--palette", str(palette)]
    if manual_scale is not None:
        cmd += ["-s", str(manual_scale)]
    # unfake prints a unicode checkmark on completion; Windows consoles default
    # to cp1252 and crash on it without this.
    subprocess.run(cmd, check=True, env={**os.environ, "PYTHONIOENCODING": "utf-8"})


def run_unfake_safe(input_path: Path, out_path: Path, colors: int, alpha: bool,
                     palette: Path | None, min_dim: int = 8) -> bool:
    """unfake's scale auto-detect can be fooled by a large uniform region (e.g.
    a flat-color background dominating the frame) into wildly over-detecting
    scale, collapsing a real sprite down to a degenerate few-pixel/single-color
    result (hit in this skill's own acceptance test: a 65x65 pixeloe output
    with a big flat gray background collapsed to 3x3/1-color). If the auto-
    detected result looks degenerate, retry once trusting pixeloe's own
    downscale (manual scale=1) instead of unfake's second-guess. Returns True
    if the fallback was used.

    Callers (converge_grid) may pass input_path == out_path to reprocess a
    file in place -- back it up first, since the initial (possibly-collapsing)
    pass would otherwise clobber the only copy the fallback needs to retry from."""
    backup = None
    if input_path == out_path:
        backup = out_path.with_name(out_path.name + ".bak")
        shutil.copy2(input_path, backup)
    try:
        run_unfake(input_path, out_path, colors, alpha, palette)
        if min(Image.open(out_path).size) < min_dim:
            run_unfake(backup or input_path, out_path, colors, alpha, palette, manual_scale=1)
            return True
        return False
    finally:
        if backup:
            backup.unlink(missing_ok=True)


def detect_scales(grid_path: Path) -> tuple[int, int]:
    out = subprocess.run(
        [str(VENV_UNFAKE_PY), "-c",
         "import unfake, numpy as np, sys; from PIL import Image; "
         "img = np.array(Image.open(sys.argv[1]).convert('RGBA')); "
         "print(unfake.runs_based_detect(img), unfake.edge_aware_detect(img))",
         str(grid_path)],
        capture_output=True, text=True, check=True,
    )
    runs, edge = out.stdout.strip().splitlines()[-1].split()
    return int(runs), int(edge)


def converge_grid(grid_path: Path, colors: int, alpha: bool,
                   palette: Path | None, max_iters: int = 3) -> int:
    """Off-grid sources (e.g. ChatGPT/Lane C) sometimes don't fully collapse to a
    true grid in one unfake pass -- keep re-running unfake on its own output
    while either detector still disagrees. edge_aware_detect can genuinely
    catch a real residual block pattern runs_based_detect misses (Lane C:
    runs==1 but edge==5 after the first pass, both hit 1 after a second) --
    but it can also permanently false-positive on a dominant-flat-background
    image that's already correct (confirmed empirically in this skill's own
    acceptance test), in which case this loop just harmlessly exhausts
    max_iters without changing anything, because run_unfake_safe() guards
    every re-run against a degenerate collapse and restores the same good
    result each time. qc_check.py's true_grid check only requires
    runs_based_detect==1 (see its docstring), so that false-positive case
    still passes QC even though this loop can't make edge_aware_detect agree."""
    for i in range(1, max_iters + 1):
        runs, edge = detect_scales(grid_path)
        if runs == 1 and edge == 1:
            return i - 1
        run_unfake_safe(grid_path, grid_path, colors, alpha, palette)
    return max_iters


def extract_palette(grid_path: Path) -> list[str]:
    out = subprocess.run(
        [str(VENV_UNFAKE_PY), "-c",
         "import unfake, numpy as np, sys, json; from PIL import Image; "
         "img = np.array(Image.open(sys.argv[1]).convert('RGBA')); "
         "print(json.dumps(unfake.extract_palette(img)))", str(grid_path)],
        capture_output=True, text=True, check=True,
    )
    return json.loads(out.stdout.strip().splitlines()[-1])


def nearest_upscale(grid_path: Path, final_path: Path, display_size: int) -> int:
    img = Image.open(grid_path)
    scale = max(1, display_size // max(img.size))
    final = img.resize((img.width * scale, img.height * scale), Image.NEAREST)
    final.save(final_path)
    return scale


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("input")
    ap.add_argument("-o", "--out-dir", default=None,
                     help="Default: alongside the input file")
    ap.add_argument("--name", help="Output basename (default: input stem)")
    ap.add_argument("--method", choices=["pixeloe", "unfake"], default="pixeloe",
                     help="pixeloe (default): full pipeline for hi-res ComfyUI output. "
                          "unfake: skip the pixeloe pass for input that's already "
                          "pixel-art-styled but off-grid (e.g. ChatGPT/DALL-E).")
    ap.add_argument("--target-size", type=int, default=64,
                     help="Target native pixel-grid resolution (art pixels, short edge). "
                          "Only used with --method pixeloe.")
    ap.add_argument("--colors", type=int, default=32)
    ap.add_argument("--display-size", type=int, default=512,
                     help="Long edge of the nearest-upscaled viewing PNG")
    ap.add_argument("--alpha", action="store_true",
                     help="Flood-fill background transparency during the unfake pass. "
                          "Works best on flat/simple backgrounds -- see "
                          "references/pixel-prompting.md. For busy AI-generated "
                          "backgrounds, run the RMBG workflow variant before pixelize.py "
                          "instead of relying on this flag.")
    ap.add_argument("--palette", help="Optional fixed palette file (hex colors, one per line)")
    args = ap.parse_args()

    input_path = Path(args.input).resolve()
    out_dir = Path(args.out_dir).resolve() if args.out_dir else input_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    name = args.name or input_path.stem

    grid_path = out_dir / f"{name}_grid.png"
    final_path = out_dir / f"{name}_final.png"
    palette_path = out_dir / f"{name}_palette.json"
    palette_arg = Path(args.palette) if args.palette else None

    if args.method == "unfake":
        unfake_input = input_path
    else:
        pixeloe_intermediate = out_dir / f"{name}_pixeloe.png"
        run_pixeloe(input_path, pixeloe_intermediate, args.target_size)
        unfake_input = pixeloe_intermediate

    if args.method == "pixeloe":
        # pixeloe already downscaled to roughly the right resolution -- if
        # unfake's auto-detect over-collapses on top of that (large uniform
        # background regions can fool it), fall back to trusting pixeloe's
        # own sizing rather than unfake's second-guess.
        used_fallback = run_unfake_safe(unfake_input, grid_path, args.colors,
                                         args.alpha, palette_arg)
        if used_fallback:
            print(f"pixelize: {name} auto-detect collapsed the grid -- "
                  f"retried with manual scale=1")
    else:
        run_unfake(unfake_input, grid_path, args.colors, args.alpha, palette_arg)
    extra_passes = converge_grid(grid_path, args.colors, args.alpha, palette_arg)
    if extra_passes:
        print(f"pixelize: {name} needed {extra_passes} extra unfake pass(es) to reach true-grid")

    scale = nearest_upscale(grid_path, final_path, args.display_size)
    palette = extract_palette(grid_path)
    palette_path.write_text(json.dumps({"colors": palette, "count": len(palette)}, indent=2))

    print(f"pixelize: {input_path.name} -> {grid_path.name} ({Image.open(grid_path).size}), "
          f"{final_path.name} (x{scale}), {len(palette)} colors")


if __name__ == "__main__":
    main()
