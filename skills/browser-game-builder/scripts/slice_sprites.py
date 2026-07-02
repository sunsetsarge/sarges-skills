#!/usr/bin/env python
"""
slice_sprites.py — turn a 3x3 sprite sheet into 8 directional game frames.

Input : one PNG laid out as a 3x3 grid — 8 unit facings around an empty center
        cell, on a plain white background (what image generators produce when
        asked for "8 directions of <unit>, top-down, white background, 3x3 grid").
Output: <key>_0.png .. <key>_7.png in --out, using the engine convention
        0=E,1=SE,2=S,3=SW,4=W,5=NW,6=N,7=NE  (frame 0 faces East/right).

Pipeline: soft white-key -> slice 9 cells -> map 8 outer cells to compass dirs
          -> trim each to content -> scale ALL frames by one common factor (keeps
          relative proportions) -> save tight transparent PNGs.

CRITICAL: image generators arrange the 8 directions inconsistently. After
slicing, ALWAYS run verify_facing.py and confirm frame 0 points right. If the
whole set is 180 off use --flip; if East/West are swapped but North/South look
right use --mirror. Both remaps are lossless and self-inverse.

Usage:
  python slice_sprites.py sheet.png crusader
  python slice_sprites.py sheet.png raptor --mirror --out assets --size 140
Requires: pillow, numpy  (any Python 3.8+; e.g. C:/AI-Shared/python.exe)
"""
import argparse, os, sys
import numpy as np
from PIL import Image

# Default "natural compass" cell layout: (col,row) -> compass frame index.
# top row = NW,N,NE ; middle = W,(empty),E ; bottom = SW,S,SE
CELL2DIR = {(0,0):5,(1,0):6,(2,0):7,
            (0,1):4,           (2,1):0,
            (0,2):3,(1,2):2,(2,2):1}

def remove_white(im):
    """Soft-key the white background to transparent (keeps light unit pixels)."""
    a = np.asarray(im.convert("RGBA")).astype(np.float32)
    r,g,b,al = a[...,0],a[...,1],a[...,2],a[...,3]
    mx = np.maximum(np.maximum(r,g),b); mn = np.minimum(np.minimum(r,g),b)
    light = np.clip((mx-200)/55.0, 0, 1)      # how bright
    flat  = np.clip((28-(mx-mn))/28.0, 0, 1)  # how low-saturation (grey/white)
    al = al * (1 - light*flat)                 # white-ish -> transparent
    a[...,3] = al
    return Image.fromarray(a.astype(np.uint8), "RGBA")

def trim(im):
    bb = im.getbbox()
    return im.crop(bb) if bb else im

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sheet"); ap.add_argument("key")
    ap.add_argument("--out", default="assets")
    ap.add_argument("--size", type=int, default=140, help="target frame height px")
    ap.add_argument("--flip", action="store_true", help="180 remap: new[i]=old[(i+4) mod 8]")
    ap.add_argument("--mirror", action="store_true", help="E/W-mirror remap: new[i]=old[(4-i) mod 8]")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    sheet = remove_white(Image.open(a.sheet))
    W,H = sheet.size; cw,ch = W//3, H//3

    # slice + trim the 8 outer cells into a dir->image dict
    by_dir = {}
    for (col,row),d in CELL2DIR.items():
        cell = sheet.crop((col*cw, row*ch, (col+1)*cw, (row+1)*ch))
        by_dir[d] = trim(cell)

    # optional facing remap (decide via verify_facing.py, never blindly)
    if a.flip:   by_dir = {i: by_dir[(i+4)%8] for i in range(8)}
    if a.mirror: by_dir = {i: by_dir[(4-i)%8] for i in range(8)}

    # one common scale so all facings keep relative proportions
    maxh = max(img.height for img in by_dir.values()) or 1
    scale = a.size / maxh
    for i in range(8):
        img = by_dir[i]
        nw,nh = max(1,round(img.width*scale)), max(1,round(img.height*scale))
        img = img.resize((nw,nh), Image.LANCZOS)
        img.save(os.path.join(a.out, f"{a.key}_{i}.png"))
    print(f"wrote {a.key}_0..7.png to {a.out}/  (verify with: "
          f"python verify_facing.py {a.key} --assets {a.out})")

if __name__ == "__main__":
    sys.exit(main())
