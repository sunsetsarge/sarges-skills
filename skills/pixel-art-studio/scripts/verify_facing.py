#!/usr/bin/env python
"""
verify_facing.py -- montage directional frames so you can confirm facing.

Copied verbatim from browser-game-builder's scripts/verify_facing.py -- it
only montages PNGs for a human/vision-model to look at, it never touches
pixel data, so there was nothing pixel-art-specific to adapt. Bundled here
too so this skill doesn't need a cross-skill script dependency at runtime.

The single most common shipping bug in a directional-sprite game is units that
move backwards, because the generated sheet was laid out mirrored or 180-rotated.
This makes that visible: render the frames with their intended compass label and
LOOK. Frame 0 must point RIGHT (East); frame 6 must point UP (North). Judge by a
barrel / nose / gun / weapon -- symmetric characters are too ambiguous to read.

Modes:
  python verify_facing.py knight                    # frames 0,2,4,6 of one key
  python verify_facing.py knight --frames 0-7        # all 8, in order
  python verify_facing.py --all                      # frame 0 of every unit
Options: --assets DIR (default assets), --out PATH (default _verify.png)

Then open/inspect the PNG (a vision model can read it directly). If frame 0
points LEFT: whole set is either 180-off (re-slice with --flip) or mirrored
(--mirror). If 0/4 look swapped but 2/6 look right, it's the mirror case.
Requires: pillow
"""
import argparse, glob, os, sys
from PIL import Image, ImageDraw

WANT = {0:"0 E>",1:"1 SE",2:"2 Sv",3:"3 SW",4:"4 W<",5:"5 NW",6:"6 N^",7:"7 NE"}

def parse_frames(s):
    if "-" in s:
        a,b = s.split("-"); return list(range(int(a),int(b)+1))
    return [int(x) for x in s.split(",")]

def cell_paste(img, d, path, x, y, cell, label):
    if os.path.exists(path):
        s = Image.open(path).convert("RGBA"); s.thumbnail((cell-10, cell-24))
        img.paste(s, (x+(cell-s.width)//2, y+4), s)
    else:
        d.text((x+6, y+cell//2), "MISSING", fill=(255,80,80))
    d.rectangle([x,y,x+cell,y+cell], outline=(90,90,100))
    d.text((x+4, y+cell-14), label, fill=(255,230,120))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("key", nargs="?")
    ap.add_argument("--frames", default="0,2,4,6")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--assets", default="assets")
    ap.add_argument("--out", default="_verify.png")
    a = ap.parse_args()
    cell = 120

    if a.all:
        keys = sorted(os.path.basename(p)[:-6] for p in glob.glob(os.path.join(a.assets,"*_0.png")))
        cols = 8; rows = (len(keys)+cols-1)//cols
        img = Image.new("RGB",(cols*cell, rows*cell),(44,46,52)); d = ImageDraw.Draw(img)
        for i,k in enumerate(keys):
            r,c = divmod(i,cols)
            cell_paste(img, d, os.path.join(a.assets,f"{k}_0.png"), c*cell, r*cell, cell, k[:15])
        img.save(a.out); print(f"{a.out}  ({len(keys)} units, frame 0 -- each must point RIGHT)")
        return

    if not a.key: ap.error("give a unit key, or --all")
    frames = parse_frames(a.frames)
    img = Image.new("RGB",(len(frames)*cell, cell),(44,46,52)); d = ImageDraw.Draw(img)
    for ci,f in enumerate(frames):
        cell_paste(img, d, os.path.join(a.assets,f"{a.key}_{f}.png"), ci*cell, 0, cell, WANT.get(f,str(f)))
    img.save(a.out); print(f"{a.out}  ({a.key}: frame 0 must point RIGHT, frame 6 UP)")

if __name__ == "__main__":
    sys.exit(main())
