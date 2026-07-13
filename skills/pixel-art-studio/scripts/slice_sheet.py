#!/usr/bin/env python
"""
slice_sheet.py -- turn a pixelized 3x3 sprite sheet into 8 directional
true-grid game frames.

This is browser-game-builder's slice_sprites.py adapted for pixel art: same
white-key removal, 3x3 slicing, compass mapping, and --flip/--mirror facing
remaps (reuse verify_facing.py from that skill unchanged -- it only montages
PNGs, it doesn't touch pixels, so there's nothing pixel-art-specific to
adapt there).

The one thing that HAD to change: the original script normalizes all 8
frames to a common height with Image.LANCZOS, which is correct for normal
sprite art but destroys true-grid pixel art (introduces anti-aliased
in-between colors, breaking every QC check downstream). This version instead
finds the largest per-frame *integer* upscale factor that keeps every frame
under the target size and applies it with Image.NEAREST -- frames end up
close to (not exactly) a common height, but every pixel in every frame stays
a flat block, matching the source, verifiable by qc_check.py the same as
any other pixelize.py output.

Input : a *_grid.png produced by pixelize.py with --method pixeloe and
        --target-size scaled up for a 3x3 grid (e.g. --target-size 192 for
        roughly 64px-native cells) run on a sheet generated white-background,
        8 facings around an empty center cell, 3x3 grid layout.
Output: <key>_0.png .. <key>_7.png in --out, using browser-game-builder's
        engine convention: 0=E,1=SE,2=S,3=SW,4=W,5=NW,6=N,7=NE (frame 0
        faces East/right).

Usage:
  python slice_sheet.py sheet_grid.png knight
  python slice_sheet.py sheet_grid.png knight --mirror --out assets --size 128
Requires: pillow, numpy (base interpreter is fine, e.g. C:/AI-Shared/python.exe)
"""
import argparse, os, sys
import numpy as np
from PIL import Image

# Same "natural compass" cell layout as browser-game-builder's slice_sprites.py.
CELL2DIR = {(0,0):5,(1,0):6,(2,0):7,
            (0,1):4,           (2,1):0,
            (0,2):3,(1,2):2,(2,2):1}


def remove_white(im, alpha_threshold=128):
    """Key the white background to transparent, then binarize alpha to 0/255.

    browser-game-builder's original remove_white() is a *soft* luminance/
    saturation key -- correct for normal sprite art, where a gradient edge
    against the background looks smooth. That soft edge is exactly what
    breaks pixel-art-studio's true-grid QC (alpha_clean requires binary
    alpha, no partial values) -- confirmed on this skill's own Phase 2 sheet
    test (a sliced frame came out with alpha values 4/60/139/255, not just
    0/255). Binarizing after the soft key keeps the same background
    detection logic but produces the hard edge true-grid pixel art needs."""
    a = np.asarray(im.convert("RGBA")).astype(np.float32)
    r, g, b, al = a[..., 0], a[..., 1], a[..., 2], a[..., 3]
    mx = np.maximum(np.maximum(r, g), b); mn = np.minimum(np.minimum(r, g), b)
    light = np.clip((mx - 200) / 55.0, 0, 1)
    flat = np.clip((28 - (mx - mn)) / 28.0, 0, 1)
    al = al * (1 - light * flat)
    al = np.where(al >= alpha_threshold, 255, 0).astype(np.float32)
    a[..., 3] = al
    return Image.fromarray(a.astype(np.uint8), "RGBA")


def trim(im):
    bb = im.getbbox()
    return im.crop(bb) if bb else im


def nearest_normalize(by_dir: dict, target_size: int) -> dict:
    """Integer-only NEAREST upscale, one common factor across all 8 frames
    (keeps relative proportions, matches pixelize.py's own nearest_upscale) --
    the factor is chosen so the tallest frame lands as close to target_size
    as possible without exceeding it."""
    maxh = max(img.height for img in by_dir.values()) or 1
    scale = max(1, target_size // maxh)
    out = {}
    for i, img in by_dir.items():
        out[i] = img.resize((img.width * scale, img.height * scale), Image.NEAREST)
    return out, scale


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sheet")
    ap.add_argument("key")
    ap.add_argument("--out", default="assets")
    ap.add_argument("--size", type=int, default=256, help="target frame height px (NEAREST, integer factor only)")
    ap.add_argument("--flip", action="store_true", help="180 remap: new[i]=old[(i+4) mod 8]")
    ap.add_argument("--mirror", action="store_true", help="E/W-mirror remap: new[i]=old[(4-i) mod 8]")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    sheet = remove_white(Image.open(a.sheet))
    W, H = sheet.size
    cw, ch = W // 3, H // 3

    by_dir = {}
    for (col, row), d in CELL2DIR.items():
        cell = sheet.crop((col * cw, row * ch, (col + 1) * cw, (row + 1) * ch))
        by_dir[d] = trim(cell)

    if a.flip:
        by_dir = {i: by_dir[(i + 4) % 8] for i in range(8)}
    if a.mirror:
        by_dir = {i: by_dir[(4 - i) % 8] for i in range(8)}

    by_dir, scale = nearest_normalize(by_dir, a.size)
    for i in range(8):
        by_dir[i].save(os.path.join(a.out, f"{a.key}_{i}.png"))

    print(f"wrote {a.key}_0..7.png to {a.out}/ (nearest x{scale}) -- verify with: "
          f"python verify_facing.py {a.key} --assets {a.out}")


if __name__ == "__main__":
    sys.exit(main())
