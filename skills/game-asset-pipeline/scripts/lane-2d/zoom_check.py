"""Render a few frames of one row at high zoom so facing / jitter can be read by eye.

Usage: zoom_check.py out.png name:row [name:row ...]
"""
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

SLICED = r"C:\Terrorier\sliced"
CELL = 300


def font(sz):
    for p in (r"C:\Windows\Fonts\arialbd.ttf", r"C:\Windows\Fonts\arial.ttf"):
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, sz)
            except Exception:
                pass
    return ImageFont.load_default()


def checker(size, step=14):
    im = Image.new("RGB", size, (62, 62, 70))
    d = ImageDraw.Draw(im)
    for y in range(0, size[1], step):
        for x in range(0, size[0], step):
            if ((x // step) + (y // step)) % 2:
                d.rectangle([x, y, x + step - 1, y + step - 1], fill=(46, 46, 54))
    return im


def main():
    out_path = sys.argv[1]
    specs = [s.split(":") for s in sys.argv[2:]]
    per = 3  # frames shown per character

    sheet = Image.new("RGB", (per * CELL, len(specs) * (CELL + 30)), (22, 22, 26))
    d = ImageDraw.Draw(sheet)
    f, fs = font(20), font(14)

    for i, (name, ri) in enumerate(specs):
        ri = int(ri)
        meta = json.load(open(os.path.join(SLICED, name, "meta.json")))
        row = meta["rows"][ri]
        # median width rejects fused slices so the zoom shows real poses
        ws = sorted(e["size"][0] for e in row)
        med = ws[len(ws) // 2]
        good = [e for e in row if e["size"][0] <= med * 1.8]
        picks = [good[0], good[len(good) // 2], good[-1]][:per]
        y = i * (CELL + 30)
        for j, ent in enumerate(picks):
            im = Image.open(os.path.join(SLICED, name, ent["file"])).convert("RGBA")
            bb = im.getchannel("A").point(lambda v: 255 if v > 12 else 0).getbbox()
            if bb:
                im = im.crop(bb)
            k = min((CELL - 20) / im.size[0], (CELL - 20) / im.size[1])
            w, h = max(1, int(im.size[0] * k)), max(1, int(im.size[1] * k))
            im = im.resize((w, h), Image.LANCZOS)
            bgc = checker((CELL, CELL))
            bgc.paste(im, ((CELL - w) // 2, (CELL - h) // 2), im)
            dd = ImageDraw.Draw(bgc)
            dd.line([(CELL // 2, 0), (CELL // 2, CELL)], fill=(255, 0, 128), width=1)
            sheet.paste(bgc, (j * CELL, y))
            d.text((j * CELL + 6, y + 4), ent["file"], fill=(255, 235, 120), font=fs)
        d.rectangle([0, y + CELL, sheet.size[0], y + CELL + 30], fill=(14, 14, 18))
        d.text((8, y + CELL + 5), f"{name}  row{ri}   [ LEFT half | RIGHT half ]",
               fill=(240, 240, 250), font=f)

    sheet.save(out_path)
    print("wrote", out_path, sheet.size)


if __name__ == "__main__":
    main()
