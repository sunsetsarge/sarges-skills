"""Facing + native-size audit.

v1's HANDOFF records that its NATIVE_RIGHT table produced wrong facing in BOTH
directions, so nothing in it is trusted here. This script renders one large,
labelled crop per character straight from C:\\Terrorier\\sliced so facing can be
read by eye (v1 trap #7: verify facing from a zoomed crop, never a screenshot).

It also prints the native frame height of every locomotion row, which sets the
encode ceiling in sync_assets.py -- we never upscale source art.
"""
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

SRC = r"C:\Terrorier"
SLICED = os.path.join(SRC, "sliced")
OUT = os.path.join(os.path.dirname(__file__), "..", "docs", "audit")

# Locomotion row per character, from v1's verified maps (tools/pack.py V3_HEROES
# and tools/row_labels.json). These row indices are trusted; the FACING baked on
# top of them is not.
LOCOMOTION = {
    "hero_base": 0,
    "hero_dusk": 1,
    "hero_frost": 0,
    "hero_inferno": 0,
    "hero_shock": 1,
    "enemy_orc_axeman": 1,
    "enemy_yeti": 1,
    "enemy_brute": 2,
    "enemy_skeleton_grunt": 1,
    "enemy_slime_pup": 2,
    "enemy_stone_golem": 1,
    "enemy_bone_archer": 1,
    "enemy_goblin_shaman": 1,
    "enemy_frost_wraith": 1,
    "enemy_shadow_hound": 1,
    "boss_elder_treant": 1,
    "boss_magma_ogre": 1,
    "boss_frost_colossus": 1,
    "boss_shadow_alpha": 1,
}

CELL = 260
LABEL_H = 34


def load_row(name, ri):
    meta_path = os.path.join(SLICED, name, "meta.json")
    if not os.path.exists(meta_path):
        return []
    meta = json.load(open(meta_path))
    rows = meta.get("rows", [])
    if ri >= len(rows):
        return []
    out = []
    for ent in rows[ri]:
        p = os.path.join(SLICED, name, ent["file"])
        if os.path.exists(p):
            out.append(Image.open(p).convert("RGBA"))
    return out


def checker(size, a=(58, 58, 66), b=(44, 44, 50), step=12):
    im = Image.new("RGB", size, a)
    d = ImageDraw.Draw(im)
    for y in range(0, size[1], step):
        for x in range(0, size[0], step):
            if ((x // step) + (y // step)) % 2:
                d.rectangle([x, y, x + step - 1, y + step - 1], fill=b)
    return im


def font(sz):
    for p in (r"C:\Windows\Fonts\arialbd.ttf", r"C:\Windows\Fonts\arial.ttf"):
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, sz)
            except Exception:
                pass
    return ImageFont.load_default()


def main():
    os.makedirs(OUT, exist_ok=True)
    names = [n for n in LOCOMOTION if os.path.isdir(os.path.join(SLICED, n))]
    names.sort()

    cols = 5
    rows_n = (len(names) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * CELL, rows_n * (CELL + LABEL_H)), (24, 24, 28))
    d = ImageDraw.Draw(sheet)
    f = font(17)
    fs = font(13)

    report = {}
    for i, name in enumerate(names):
        frames = load_row(name, LOCOMOTION[name])
        cx = (i % cols) * CELL
        cy = (i // cols) * (CELL + LABEL_H)
        if not frames:
            d.text((cx + 8, cy + 8), name + " MISSING", fill=(255, 90, 90), font=f)
            report[name] = {"error": "no frames"}
            continue

        # middle frame of the row is the most representative pose
        fr = frames[len(frames) // 2]
        bb = fr.getchannel("A").point(lambda v: 255 if v > 12 else 0).getbbox()
        if bb:
            fr = fr.crop(bb)
        heights = sorted(
            (im.getchannel("A").point(lambda v: 255 if v > 12 else 0).getbbox() or (0, 0, 1, 1))[3]
            - (im.getchannel("A").point(lambda v: 255 if v > 12 else 0).getbbox() or (0, 0, 1, 1))[1]
            for im in frames
        )
        native_h = heights[len(heights) // 2]
        report[name] = {
            "row": LOCOMOTION[name],
            "frames": len(frames),
            "native_median_h": native_h,
            "frame_size": list(fr.size),
        }

        k = min((CELL - 16) / fr.size[0], (CELL - 16) / fr.size[1])
        w, h = max(1, int(fr.size[0] * k)), max(1, int(fr.size[1] * k))
        fr = fr.resize((w, h), Image.LANCZOS)

        bgc = checker((CELL, CELL))
        bgc.paste(fr, ((CELL - w) // 2, (CELL - h) // 2), fr)
        sheet.paste(bgc, (cx, cy))
        # arrow marks screen-right so facing is unambiguous when read back
        d.rectangle([cx, cy + CELL, cx + CELL, cy + CELL + LABEL_H], fill=(16, 16, 20))
        d.text((cx + 6, cy + CELL + 3), name, fill=(235, 235, 245), font=f)
        d.text((cx + 6, cy + CELL + 20), f"row{LOCOMOTION[name]}  {len(frames)}f  h={native_h}px  -->screen right",
               fill=(150, 150, 165), font=fs)

    p = os.path.join(OUT, "facing_audit.png")
    sheet.save(p)
    json.dump(report, open(os.path.join(OUT, "native_sizes.json"), "w"), indent=1)
    print("wrote", p, sheet.size)
    for k, v in sorted(report.items()):
        print(f"  {k:26s} {v}")


if __name__ == "__main__":
    sys.exit(main())
