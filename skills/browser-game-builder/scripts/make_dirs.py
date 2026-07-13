#!/usr/bin/env python
"""
make_dirs.py — derive 8 rotation-based directional frames from one East-facing
canonical overhead sprite.

ONLY for true-overhead (top-down ~90 degree) art -- infantry, heli bodies, etc.
3/4-view art (tanks, most vehicles) has a baked horizon/perspective and rotating
it produces a unit that looks like it's tipping over -- those sets must NOT go
through this tool; keep using slice_sprites.py / individual regeneration for them.

Facing convention (engine): frame 0 = East, then CLOCKWISE IN SCREEN SPACE
(canvas y points down): 1=SE, 2=S (down), 3=SW, 4=W, 5=NW, 6=N (up), 7=NE.
The insight this tool exploits: for true-overhead art, ALL 8 facings are the
same sprite at different rotations, so deriving them programmatically from one
canonical East frame makes size and facing correct BY CONSTRUCTION -- no more
per-frame AI drift (mirrored diagonals, mismatched scale between units, etc).

Pipeline:
  1. trim input to its alpha bbox
  2. uniform-scale so the content HEIGHT == --height H
  3. paste centered on a square transparent canvas of side ceil(H*1.5)
     (headroom so rotated corners never clip the canvas edge)
  4. for i in 0..7: rotate by i * ROTATE_STEP_DEG and save frame i

Rotation sign: PIL's Image.rotate(angle) rotates COUNTER-clockwise as the image
is displayed, in standard image coordinates (origin top-left, y increases
downward -- the same convention this game's canvas uses). A screen-space
CLOCKWISE turn (what the engine's facing convention needs: frame 0 East ->
frame 2 South/down) therefore requires a NEGATIVE angle passed to
Image.rotate(). This was VERIFIED EMPIRICALLY, not just reasoned out: an
asymmetric right-pointing arrow test image, run through this exact pipeline,
lands its frame 2 pointing straight DOWN and its frame 6 pointing straight UP
with ROTATE_STEP_DEG = -45 (confirmed by measuring the arrow tip's offset from
the frame's center of mass). Do not flip this sign without re-deriving it the
same way -- the assumption "clockwise compass = negative PIL angle" bit the
plan's authors once already (see FINISH_PLAN.md WS-A1 note).

Usage:
  python make_dirs.py ranger_east.png ranger --height 120 --out assets
  python make_dirs.py ranger_walk_east.png ranger --height 120 --out assets --pose 1
Requires: pillow
"""
import argparse, math, os, sys
from PIL import Image

# Negative = clockwise in screen space (y-down canvas). See docstring above --
# verified empirically with an asymmetric arrow test, not assumed.
ROTATE_STEP_DEG = -45.0


def trim(im):
    bb = im.getbbox()
    return im.crop(bb) if bb else im


def build_canvas(src_path, height):
    """Trim to alpha bbox -> scale so content height == H -> center on a
    square transparent canvas with rotation headroom. Returns (canvas, side)."""
    im = Image.open(src_path).convert("RGBA")
    im = trim(im)
    if im.width == 0 or im.height == 0:
        raise ValueError(f"{src_path}: fully transparent, nothing to trim")
    scale = height / im.height
    nw, nh = max(1, round(im.width * scale)), max(1, round(im.height * scale))
    im = im.resize((nw, nh), Image.LANCZOS)
    side = math.ceil(height * 1.5)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(im, ((side - nw) // 2, (side - nh) // 2), im)
    return canvas, side


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("east_png", help="East-facing RGBA source frame, transparent background")
    ap.add_argument("key")
    ap.add_argument("--height", type=int, required=True, help="target content height in px")
    ap.add_argument("--out", default="assets")
    ap.add_argument("--pose", type=int, default=0,
                     help="pose index for future walk frames; 0 (default) writes <key>_0..7.png, "
                          "N>0 writes <key>_p<N>_0..7.png")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    canvas, side = build_canvas(a.east_png, a.height)

    written = []
    for i in range(8):
        angle = ROTATE_STEP_DEG * i
        frame = canvas.rotate(angle, resample=Image.BICUBIC, expand=False)
        name = f"{a.key}_{i}.png" if a.pose == 0 else f"{a.key}_p{a.pose}_{i}.png"
        frame.save(os.path.join(a.out, name))
        written.append(name)

    print(f"{a.key}: H={a.height} canvas={side}x{side} pose={a.pose} "
          f"wrote {len(written)} files to {a.out}/ ({written[0]}..{written[-1]})")


if __name__ == "__main__":
    sys.exit(main())
