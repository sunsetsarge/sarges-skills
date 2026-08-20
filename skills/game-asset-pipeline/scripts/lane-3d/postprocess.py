"""
Post-process raw Blender renders into final game sprite frames.

For each unit: union the alpha-bbox across all its frames, pad +4px, crop every
frame with that SAME box, scale down (never up) to height <= 512 (LANCZOS),
same scale factor for every frame of that unit. Save to assets/frames/.
"""
from PIL import Image
import os

RENDER_DIR = r"C:\Claude\Projects\Active\Beachhead\meshy_test\renders"
OUT_DIR = r"C:\Claude\Projects\Active\Beachhead\assets\frames"
os.makedirs(OUT_DIR, exist_ok=True)

UNITS = {
    "infantry": 8,
    "commando": 8,
    "tank": 1,
    "landing_craft": 1,
    "helicopter": 1,
}

MAX_HEIGHT = 512
PAD = 4

for unit, nframes in UNITS.items():
    paths = [os.path.join(RENDER_DIR, f"{unit}_{i}.png") for i in range(nframes)]
    imgs = [Image.open(p).convert("RGBA") for p in paths]

    # union bbox across all frames (alpha channel non-transparent extent)
    union_box = None
    for im in imgs:
        alpha = im.split()[-1]
        bbox = alpha.getbbox()
        if bbox is None:
            continue
        if union_box is None:
            union_box = list(bbox)
        else:
            union_box[0] = min(union_box[0], bbox[0])
            union_box[1] = min(union_box[1], bbox[1])
            union_box[2] = max(union_box[2], bbox[2])
            union_box[3] = max(union_box[3], bbox[3])

    if union_box is None:
        raise RuntimeError(f"No non-transparent pixels found for unit {unit}")

    w, h = imgs[0].size
    left = max(0, union_box[0] - PAD)
    top = max(0, union_box[1] - PAD)
    right = min(w, union_box[2] + PAD)
    bottom = min(h, union_box[3] + PAD)
    crop_box = (left, top, right, bottom)
    crop_h = bottom - top

    # single scale factor for this unit, computed once from union-box height, never upscale
    scale = min(1.0, MAX_HEIGHT / crop_h)

    for i, im in enumerate(imgs):
        cropped = im.crop(crop_box)
        new_w = max(1, round(cropped.width * scale))
        new_h = max(1, round(cropped.height * scale))
        if scale < 1.0:
            resized = cropped.resize((new_w, new_h), Image.LANCZOS)
        else:
            resized = cropped
        out_path = os.path.join(OUT_DIR, f"{unit}_{i}.png")
        resized.save(out_path)
        print(f"{unit}_{i}.png -> {resized.size} (crop_box={crop_box}, scale={scale:.4f})")

print("POSTPROCESS DONE")
