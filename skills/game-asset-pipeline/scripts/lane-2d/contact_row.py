"""Render EVERY frame of a row with its index, so turntable rows can be read and
a usable facing angle hand-picked.

Usage: contact_row.py out.png CELL name:row [name:row ...]
"""
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

SLICED = r"C:\Terrorier\sliced"


def font(sz):
    for p in (r"C:\Windows\Fonts\arialbd.ttf", r"C:\Windows\Fonts\arial.ttf"):
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, sz)
            except Exception:
                pass
    return ImageFont.load_default()


def checker(size, step=10):
    im = Image.new("RGB", size, (62, 62, 70))
    d = ImageDraw.Draw(im)
    for y in range(0, size[1], step):
        for x in range(0, size[0], step):
            if ((x // step) + (y // step)) % 2:
                d.rectangle([x, y, x + step - 1, y + step - 1], fill=(46, 46, 54))
    return im


def main():
    out_path, cell = sys.argv[1], int(sys.argv[2])
    specs = [s.split(":") for s in sys.argv[3:]]
    rows = []
    for name, ri in specs:
        meta = json.load(open(os.path.join(SLICED, name, "meta.json")))
        rows.append((name, int(ri), meta["rows"][int(ri)]))

    cols = max(len(r[2]) for r in rows)
    sheet = Image.new("RGB", (cols * cell, len(rows) * (cell + 26)), (22, 22, 26))
    d = ImageDraw.Draw(sheet)
    f, fs = font(16), font(12)

    for i, (name, ri, row) in enumerate(rows):
        y = i * (cell + 26)
        for j, ent in enumerate(row):
            im = Image.open(os.path.join(SLICED, name, ent["file"])).convert("RGBA")
            bb = im.getchannel("A").point(lambda v: 255 if v > 12 else 0).getbbox()
            if bb:
                im = im.crop(bb)
            k = min((cell - 8) / im.size[0], (cell - 8) / im.size[1])
            w, h = max(1, int(im.size[0] * k)), max(1, int(im.size[1] * k))
            im = im.resize((w, h), Image.LANCZOS)
            bgc = checker((cell, cell))
            bgc.paste(im, ((cell - w) // 2, (cell - h) // 2), im)
            dd = ImageDraw.Draw(bgc)
            dd.line([(cell // 2, 0), (cell // 2, cell)], fill=(255, 0, 128))
            dd.text((3, 2), str(j), fill=(255, 240, 90), font=fs)
            sheet.paste(bgc, (j * cell, y))
        d.rectangle([0, y + cell, sheet.size[0], y + cell + 26], fill=(14, 14, 18))
        d.text((6, y + cell + 4), f"{name} row{ri}  ({len(row)} frames)",
               fill=(240, 240, 250), font=f)

    sheet.save(out_path)
    print("wrote", out_path, sheet.size)


if __name__ == "__main__":
    main()
