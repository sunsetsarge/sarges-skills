"""Zoomed QA of the PACKED sheets (post-defringe) -- the output the game loads.

Halos, clipped edges and baseline drift are only judgeable here, at size, on a
dark background. Usage: qa_packed.py out.png ZOOM key:anim [key:anim ...]
"""
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

PROJ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ASSETS = os.path.join(PROJ, "public", "assets")


def font(sz):
    try:
        return ImageFont.truetype(r"C:\Windows\Fonts\arialbd.ttf", sz)
    except Exception:
        return ImageFont.load_default()


def main():
    out_path, zoom = sys.argv[1], float(sys.argv[2])
    specs = [s.split(":") for s in sys.argv[3:]]
    man = json.load(open(os.path.join(ASSETS, "manifest.json")))

    rows = []
    for key, anim in specs:
        e = man["sprites"][key]
        a = e["anims"][anim]
        img = Image.open(os.path.join(ASSETS, e["file"])).convert("RGBA")
        cw, ch = int(e["cellW"] * zoom), int(e["cellH"] * zoom)
        frames = []
        for j in range(a["frames"]):
            fr = img.crop((j * e["cellW"], a["row"] * e["cellH"],
                           (j + 1) * e["cellW"], (a["row"] + 1) * e["cellH"]))
            frames.append(fr.resize((cw, ch), Image.NEAREST))
        rows.append((f"{key}.{anim}", frames, cw, ch))

    W = max(len(f) * cw for _, f, cw, _ in rows)
    H = sum(ch + 24 for _, _, _, ch in rows)
    sheet = Image.new("RGB", (W, H), (18, 18, 22))
    d = ImageDraw.Draw(sheet)
    f = font(15)

    y = 0
    for label, frames, cw, ch in rows:
        # ground line: packed frames are bottom-anchored, so feet must sit here
        d.line([(0, y + ch - 1), (W, y + ch - 1)], fill=(255, 40, 120))
        for j, fr in enumerate(frames):
            sheet.paste(fr, (j * cw, y), fr)
            d.rectangle([j * cw, y, j * cw + cw - 1, y + ch - 1], outline=(60, 60, 72))
        d.rectangle([0, y + ch, W, y + ch + 24], fill=(10, 10, 14))
        d.text((6, y + ch + 4), label + "   (red line = ground anchor)",
               fill=(240, 240, 250), font=f)
        y += ch + 24

    sheet.save(out_path)
    print("wrote", out_path, sheet.size)


if __name__ == "__main__":
    main()
