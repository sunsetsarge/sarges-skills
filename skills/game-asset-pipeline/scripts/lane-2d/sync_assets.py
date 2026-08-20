"""Frames -> game-ready sprite atlas + manifest.json.

Stage B of the pipeline. Takes the per-frame PNGs that slice_sheet.py cut out of
white-matte grid sheets, plus an authored asset_jobs.json saying which row is
which animation, and emits one WebP grid per character.

Why this shape:

  * ONE WebP per character, laid out as a uniform grid: row = animation,
    column = frame. Transparent padding costs almost nothing in WebP and it
    keeps the request count at ~20 instead of ~130.

  * Every frame of an animation is cropped to that animation's UNION alpha box,
    never to its own box. Trimming each frame separately produces run-cycle
    jitter: many sheets have a baked drop shadow that appears in some frames and
    not others, which moves the anchor from frame to frame. A shared crop box
    makes intra-animation jitter structurally impossible.

  * Facing is baked once, here, from the table in asset_jobs.json, which must be
    read off zoomed contact sheets rather than guessed. Nothing is mirrored at
    draw time -- runtime flipping means every new sheet needs a correct lookup
    entry, and one wrong entry makes a character run backwards.

  * Partially transparent pixels are un-premultiplied against the white matte
    to kill the halo that white-background keying leaves behind.

Usage:
    python sync_assets.py --root ART_ROOT [--jobs J] [--out O] [--contact]
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))

# Set from CLI in main(). Module-level because the pack/QA helpers below read
# them; keeping them as globals avoids threading a config object through every
# function for a script that only ever runs once per invocation.
OUT_DIR = ""
AUDIT_DIR = ""
REF_W, REF_H = 390, 844
SUPERSAMPLE = 2.0          # encode at most 2x the on-screen size ...
WEBP_Q = 82                # ... v1 trap #5: alpha below q~70 blocks up the edge
BG_HEIGHT = 420            # every parallax band is exported at this height
WEATHER_W = 768

FPS = {"run": 14, "walk": 10, "idle": 8, "attack": 16, "special": 14,
       "hurt": 12, "death": 10, "victory": 10}
DEFAULT_FPS = 12

ALPHA_CUT = 12             # below this, a pixel is background, not art


class Fail(Exception):
    pass


# ---------------------------------------------------------------- frame utils

def alpha_box(im: Image.Image):
    return im.getchannel("A").point(lambda v: 255 if v > ALPHA_CUT else 0).getbbox()


def union_box(frames):
    boxes = [alpha_box(f) for f in frames]
    boxes = [b for b in boxes if b]
    if not boxes:
        return None
    return (min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes))


def defringe(im: Image.Image) -> Image.Image:
    """Un-premultiply edge pixels against the white matte they were keyed from.

    White-background keying leaves a bright halo on every antialiased edge: the
    observed colour of a partial pixel is (a*C + (1-a)*255). Recovering C makes
    the edge read as the artwork's own outline instead of a glow. Fully opaque
    pixels are untouched, so a genuine white stroke in the art survives.
    """
    im = im.convert("RGBA")
    px = im.load()
    w, h = im.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a == 0 or a >= 250:
                continue
            f = a / 255.0
            nr = (r - 255.0 * (1.0 - f)) / f
            ng = (g - 255.0 * (1.0 - f)) / f
            nb = (b - 255.0 * (1.0 - f)) / f
            px[x, y] = (max(0, min(255, int(nr + 0.5))),
                        max(0, min(255, int(ng + 0.5))),
                        max(0, min(255, int(nb + 0.5))), a)
    return im


def load_rows(root, key):
    d = os.path.join(root, "sliced", key)
    meta_path = os.path.join(d, "meta.json")
    if not os.path.exists(meta_path):
        raise Fail(f"{key}: no sliced/{key}/meta.json -- run v1's tools/slice.py first")
    meta = json.load(open(meta_path))
    rows = []
    for row in meta.get("rows", []):
        frames = []
        for ent in row:
            p = os.path.join(d, ent["file"])
            if os.path.exists(p):
                frames.append(p)
        rows.append(frames)
    return rows


def select_frames(key, anim, spec, rows):
    """Row -> candidate frames, honouring the authored take/drop window only.

    Outlier rejection happens later, in reject_outliers(), against a median
    taken over the WHOLE character. Judging a frame against its own row is not
    enough: a row can be mostly fused (Yeti) or hold only two poses, and then
    the row median is itself the outlier.
    """
    ri = spec["row"]
    if ri >= len(rows) or not rows[ri]:
        raise Fail(f"{key}.{anim}: row {ri} does not exist")
    paths = list(rows[ri])

    if "take" in spec:
        a, b = spec["take"]
        paths = paths[a:b + 1]
    for i in sorted(spec.get("drop", []), reverse=True):
        if 0 <= i < len(paths):
            del paths[i]
    if not paths:
        raise Fail(f"{key}.{anim}: every frame was dropped")

    return [Image.open(p).convert("RGBA") for p in paths]


def _median(xs):
    xs = sorted(xs)
    return xs[len(xs) // 2] if xs else 1


def reject_outliers(key, picked, report):
    """Drop fused slices and caption strips, measured against the character.

    A fused slice contains two creatures and is far wider than a real pose; a
    caption strip ("WALK LEFT" baked into the sheet) is far shorter. Both must
    go before union boxes are taken, because a single survivor stretches the
    union box for its whole animation and shrinks the artwork to a speck
    inside an enormous cell.
    """
    boxes = {}
    for anim, frames in picked.items():
        boxes[anim] = [alpha_box(f) for f in frames]

    all_w = [b[2] - b[0] for v in boxes.values() for b in v if b]
    all_h = [b[3] - b[1] for v in boxes.values() for b in v if b]
    med_w, med_h = _median(all_w), _median(all_h)

    out, dropped = {}, 0
    for anim, frames in picked.items():
        keep = []
        for f, b in zip(frames, boxes[anim]):
            if not b:
                dropped += 1
                continue
            w, h = b[2] - b[0], b[3] - b[1]
            if w > med_w * 1.75 or h < med_h * 0.45 or h > med_h * 2.0:
                dropped += 1
                continue
            keep.append(f)
        if not keep:
            report.setdefault("warnings", []).append(
                f"{key}.{anim}: all frames rejected as fused/caption -- animation skipped")
            continue

        # Final guard: a survivor can still stretch the union box (two poses
        # that only overlap slightly). Tighten until the union is sane.
        for limit in (1.75, 1.35, 1.15):
            ub = union_box(keep)
            if ub and (ub[2] - ub[0]) <= med_w * 2.0:
                break
            tighter = [f for f in keep
                       if (alpha_box(f)[2] - alpha_box(f)[0]) <= med_w * limit]
            if tighter:
                dropped += len(keep) - len(tighter)
                keep = tighter
        out[anim] = keep
    return out, dropped


# ---------------------------------------------------------------- characters

def pack_character(root, key, spec, want_facing, report):
    rows = load_rows(root, key)
    anims_spec = spec["anims"]

    picked = {}
    for anim, aspec in anims_spec.items():
        try:
            picked[anim] = select_frames(key, anim, aspec, rows)
        except Fail as e:
            report.setdefault("warnings", []).append(str(e))
    if not picked:
        raise Fail(f"{key}: no usable animations")

    picked, total_dropped = reject_outliers(key, picked, report)
    if not picked:
        raise Fail(f"{key}: every animation was rejected as fused/caption")

    mirror = spec["facing"] != "frontal" and spec["facing"] != want_facing

    # crop each animation to its own union box -> no intra-animation jitter
    cropped = {}
    for anim, frames in picked.items():
        ub = union_box(frames)
        if not ub:
            continue
        cut = [f.crop(ub) for f in frames]
        if mirror:
            cut = [f.transpose(Image.FLIP_LEFT_RIGHT) for f in cut]
        cropped[anim] = cut
    if not cropped:
        raise Fail(f"{key}: every animation was empty after cropping")

    # scale is anchored to the locomotion pose so idle/attack keep their
    # relative size; v1 trap #1 -- never scale a frame by its own bbox
    ref = None
    for cand in ("run", "walk", "idle", "a", "h0"):
        if cand in cropped:
            ref = cropped[cand]
            break
    if ref is None:
        ref = list(cropped.values())[0]
    ref_h = ref[0].size[1]

    display_h = float(spec["displayH"])
    enc_h = min(float(ref_h), display_h * SUPERSAMPLE)   # never upscale source art
    k = enc_h / float(ref_h)
    draw_scale = display_h / enc_h

    scaled = {}
    for anim, frames in cropped.items():
        out = []
        for f in frames:
            w = max(1, int(round(f.size[0] * k)))
            h = max(1, int(round(f.size[1] * k)))
            out.append(f.resize((w, h), Image.LANCZOS))
        scaled[anim] = out

    cell_w = max(f.size[0] for v in scaled.values() for f in v)
    cell_h = max(f.size[1] for v in scaled.values() for f in v)
    cols = max(len(v) for v in scaled.values())
    order = sorted(scaled.keys())

    sheet = Image.new("RGBA", (cols * cell_w, len(order) * cell_h), (0, 0, 0, 0))
    anims_meta = {}
    for ri, anim in enumerate(order):
        for ci, f in enumerate(scaled[anim]):
            # bottom-centre inside the cell: the union box's bottom edge is the
            # character's ground contact, so every animation lines up on the floor
            x = ci * cell_w + (cell_w - f.size[0]) // 2
            y = ri * cell_h + (cell_h - f.size[1])
            sheet.paste(f, (x, y), f)
        anims_meta[anim] = {"row": ri, "frames": len(scaled[anim]),
                            "fps": FPS.get(anim, DEFAULT_FPS)}

    sheet = defringe(sheet)

    rel = f"sprites/{key}.webp"
    path = os.path.join(OUT_DIR, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    sheet.save(path, "WEBP", quality=WEBP_Q, method=6, exact=True)

    entry = {
        "file": rel, "cellW": cell_w, "cellH": cell_h,
        "cols": cols, "rowCount": len(order),
        "drawScale": round(draw_scale, 5),
        "displayH": spec["displayH"],
        "mirrored": mirror,
        "anims": anims_meta,
    }
    if spec.get("degraded"):
        entry["degraded"] = spec["degraded"]
    report["sprites"][key] = {
        "bytes": os.path.getsize(path), "cell": [cell_w, cell_h],
        "anims": {a: len(v) for a, v in scaled.items()},
        "dropped_frames": total_dropped, "mirrored": mirror,
    }
    return entry


# ---------------------------------------------------------------- background

def pack_backgrounds(root, jobs, manifest, report):
    out = {}
    for stage, cfg in jobs.get("backgrounds", {}).items():
        if stage.startswith("_"):
            continue
        layers = []
        for name in cfg["layers"]:
            src = os.path.join(root, cfg["dir"].replace("/", os.sep), name + ".png")
            if not os.path.exists(src):
                report.setdefault("warnings", []).append(f"background missing: {src}")
                continue
            im = Image.open(src).convert("RGB")
            k = BG_HEIGHT / im.size[1]
            im = im.resize((max(1, int(im.size[0] * k)), BG_HEIGHT), Image.LANCZOS)
            rel = f"bg/{stage}_{name}.webp"
            p = os.path.join(OUT_DIR, rel)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            im.save(p, "WEBP", quality=80, method=6)
            layers.append({"name": name, "file": rel, "w": im.size[0], "h": im.size[1],
                           "bytes": os.path.getsize(p)})
        out[stage] = {"layers": layers}
        report["backgrounds"][stage] = sum(l["bytes"] for l in layers)
    manifest["backgrounds"] = out


def pack_weather(root, jobs, manifest, report):
    out = {}
    for name, rel_src in jobs.get("weather", {}).items():
        if name.startswith("_"):
            continue
        src = os.path.join(root, rel_src.replace("/", os.sep))
        if not os.path.exists(src):
            report.setdefault("warnings", []).append(f"weather missing: {src}")
            continue
        im = Image.open(src).convert("RGB")
        k = WEATHER_W / im.size[0]
        im = im.resize((WEATHER_W, max(1, int(im.size[1] * k))), Image.LANCZOS)
        rel = f"weather/{name}.webp"
        p = os.path.join(OUT_DIR, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        im.save(p, "WEBP", quality=78, method=6)
        out[name] = {"file": rel, "w": im.size[0], "h": im.size[1], "blend": "lighter"}
        report["weather"][name] = os.path.getsize(p)
    manifest["weather"] = out


# ---------------------------------------------------------------- contact QA

def contact_sheet(manifest, path):
    """Render every packed animation so slicing quality can be judged by eye."""
    cellpx = 96
    rows = []
    for key, e in sorted(manifest["sprites"].items()):
        for anim, a in sorted(e["anims"].items()):
            rows.append((key, anim, e, a))
    cols = max(a["frames"] for _, _, _, a in rows)
    W = 180 + cols * cellpx
    H = len(rows) * cellpx
    sheet = Image.new("RGB", (W, H), (26, 26, 32))
    d = ImageDraw.Draw(sheet)
    try:
        f = ImageFont.truetype(r"C:\Windows\Fonts\arialbd.ttf", 13)
    except Exception:
        f = ImageFont.load_default()

    # checkerboard so halos and clipped edges are visible
    step = 8
    for y in range(0, H, step):
        for x in range(180, W, step):
            if ((x // step) + (y // step)) % 2:
                d.rectangle([x, y, x + step - 1, y + step - 1], fill=(40, 40, 48))

    for i, (key, anim, e, a) in enumerate(rows):
        img = Image.open(os.path.join(OUT_DIR, e["file"])).convert("RGBA")
        y = i * cellpx
        d.text((6, y + cellpx // 2 - 8), f"{key}", fill=(235, 235, 245), font=f)
        d.text((6, y + cellpx // 2 + 6), f"  {anim} x{a['frames']}", fill=(150, 150, 165), font=f)
        for j in range(a["frames"]):
            fr = img.crop((j * e["cellW"], a["row"] * e["cellH"],
                           (j + 1) * e["cellW"], (a["row"] + 1) * e["cellH"]))
            k = min((cellpx - 6) / fr.size[0], (cellpx - 6) / fr.size[1])
            fr = fr.resize((max(1, int(fr.size[0] * k)), max(1, int(fr.size[1] * k))),
                           Image.LANCZOS)
            sheet.paste(fr, (180 + j * cellpx + (cellpx - fr.size[0]) // 2,
                             y + cellpx - fr.size[1]), fr)
        d.line([(0, y), (W, y)], fill=(70, 70, 82))
    sheet.save(path)
    return sheet.size


# ---------------------------------------------------------------- main

def main():
    global OUT_DIR, AUDIT_DIR, REF_W, REF_H
    ap = argparse.ArgumentParser(
        description="Pack sliced frames into per-character WebP grids + manifest.json")
    ap.add_argument("--root", default=os.environ.get("ASSET_SOURCE_ROOT", "."),
                    help="Asset source root. Must contain sliced/<key>/meta.json "
                         "(output of slice_sheet.py) and any background/weather art.")
    ap.add_argument("--jobs", default=None,
                    help="Path to asset_jobs.json. Default: <root>/asset_jobs.json")
    ap.add_argument("--out", default=None,
                    help="Output dir for sprites/ and manifest.json. "
                         "Default: <root>/public/assets")
    ap.add_argument("--audit", default=None,
                    help="Where QA images go. Default: <out>/../audit")
    ap.add_argument("--ref", default="390x844",
                    help="Reference design resolution, WxH. Default 390x844 (portrait phone)")
    ap.add_argument("--contact", action="store_true",
                    help="Also render a contact sheet of every packed animation. "
                         "Look at it -- frame counts never prove a row is correct.")
    args = ap.parse_args()

    root = args.root
    if not os.path.isdir(root):
        print(f"FATAL: asset root does not exist: {root}", file=sys.stderr)
        return 2
    if "x" in args.ref:
        REF_W, REF_H = (int(v) for v in args.ref.lower().split("x", 1))

    OUT_DIR = args.out or os.path.join(root, "public", "assets")
    AUDIT_DIR = args.audit or os.path.join(os.path.dirname(OUT_DIR.rstrip("/\\")), "audit")

    jobs_path = args.jobs or os.path.join(root, "asset_jobs.json")
    if not os.path.exists(jobs_path):
        print(f"FATAL: no jobs file at {jobs_path}\n"
              f"       Author one first -- see references/lane-2d-sheets.md "
              f"(Stage B / 'The job spec').", file=sys.stderr)
        return 2
    jobs = json.load(open(jobs_path))
    if os.path.isdir(os.path.join(OUT_DIR, "sprites")):
        shutil.rmtree(os.path.join(OUT_DIR, "sprites"))
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(AUDIT_DIR, exist_ok=True)

    manifest = {"version": 1, "reference": {"w": REF_W, "h": REF_H},
                "source": root, "sprites": {}}
    report = {"sprites": {}, "backgrounds": {}, "weather": {}, "warnings": []}

    groups = [("heroes", "right"), ("enemies", "left"),
              ("bosses", "left"), ("props", "left")]
    for group, want in groups:
        for key, spec in jobs.get(group, {}).items():
            if key.startswith("_"):
                continue
            try:
                manifest["sprites"][key] = pack_character(root, key, spec, want, report)
            except Fail as e:
                report["warnings"].append(str(e))
                print("  WARN", e)

    pack_backgrounds(root, jobs, manifest, report)
    pack_weather(root, jobs, manifest, report)

    manifest["unusable"] = {k: v for k, v in jobs.get("_unusable", {}).items()
                            if not k.startswith("_")}

    with open(os.path.join(OUT_DIR, "manifest.json"), "w") as fh:
        json.dump(manifest, fh, indent=1)

    total = (sum(v["bytes"] for v in report["sprites"].values())
             + sum(report["backgrounds"].values())
             + sum(report["weather"].values()))
    report["total_bytes"] = total
    with open(os.path.join(AUDIT_DIR, "sync_report.json"), "w") as fh:
        json.dump(report, fh, indent=1)

    print(f"\n{len(manifest['sprites'])} sprite sheets, "
          f"{len(manifest['backgrounds'])} stages, {len(manifest['weather'])} weather")
    for k, v in sorted(report["sprites"].items()):
        flag = "  MIRRORED" if v["mirrored"] else ""
        dropped = f"  dropped={v['dropped_frames']}" if v["dropped_frames"] else ""
        print(f"  {k:24s} {v['bytes']//1024:4d}KB cell={v['cell']} {v['anims']}{flag}{dropped}")
    print(f"\n  backgrounds {sum(report['backgrounds'].values())//1024}KB"
          f"   weather {sum(report['weather'].values())//1024}KB")
    print(f"  TOTAL {total/1048576:.2f} MB uncompressed-on-disk")
    if report["warnings"]:
        print("\nWARNINGS:")
        for w in report["warnings"]:
            print("  -", w)

    if args.contact:
        p = os.path.join(AUDIT_DIR, "contact_all.png")
        print("\ncontact sheet:", p, contact_sheet(manifest, p))
    return 0


if __name__ == "__main__":
    sys.exit(main())
