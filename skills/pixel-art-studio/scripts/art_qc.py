"""Art-correctness QC. The other half of qc_check.py.

qc_check.py verifies the art is a valid *pixel grid*: true-grid resolution,
color count, binary alpha, exact integer upscale. It says nothing about
whether the art is any good, and nothing at all about how frames relate to
each other.

This one measures the art itself:

  sprite  -- outline_coverage, baseline_alignment, alpha_crispness
  frames  -- silhouette_iou, bbox_drift_x/y  (frame-to-frame consistency)

The frame metrics are the point. references/sprite-sheets.md closes on an
open question -- "untested whether a 3rd/4th intermediate frame stays as
consistent, or whether identity drift creeps in over more edit passes" --
and the only way it could have been answered before now was by eye. Drift is
exactly what silhouette_iou and bbox_drift measure, so run this on any
multi-frame Qwen-Edit output before deciding the cycle holds.

Precondition, and it is a real one: feed it CHARACTER-ISOLATED frames
(transparent everywhere but the character). Frames that still carry scenery
or VFX score that scenery's movement instead -- see opaque_fraction below,
which documents how this skill's own eval frames fall into that trap.

Run BOTH: qc_check.py for grid validity, this for art validity. Neither
subsumes the other.

Pure Pillow -- runs on the base interpreter (C:\\AI-Shared\\python.exe).
Ported from ianlintner/ai-pixel-art-image-generation (MIT), see
THIRD-PARTY.md. Divergences from upstream, both deliberate:
  - palette_fidelity is reported but NEVER gates. Upstream hard-fails
    anything that is not 100% on a named palette, which is only meaningful
    if you force-quantize to one. This skill's Lane A/B/C use unfake's
    adaptive per-image palettes, where the metric is meaningless by
    construction.
  - outline_coverage is soft. A deliberate no-outline style is a legitimate
    choice, not a defect.

Usage:
  python art_qc.py sprite knight_grid.png
  python art_qc.py frames walk_a_grid.png walk_b_grid.png [...]
  python art_qc.py sheet walk_sheet.png --tile-size 32 --frames 4
"""
import argparse
import json
import sys
from pathlib import Path

from PIL import Image

# Gate table. 'hard' failures exit non-zero; 'soft' ones print a warning.
# Every threshold is upstream's starting value -- treat them as calibrated
# for upstream's art, not as constants. Re-tune against your own known-good
# output before trusting a FAIL.
GATES = {
    "alpha_crispness":  {"op": "ge", "value": 0.999, "hard": True},
    "baseline_alignment": {"op": "eq", "value": True, "hard": True},
    "outline_coverage": {"op": "ge", "value": 0.85, "hard": False},
    "silhouette_iou":   {"op": "ge", "value": 0.85, "hard": True},
    # x-drift is loose on purpose: a walk cycle's contact pose (legs extended)
    # is legitimately several px wider than its passing pose (legs crossed).
    # This gate catches the character changing SIZE, not changing pose.
    "bbox_drift_x":     {"op": "le", "value": 6, "hard": True},
    # y-drift is tight: vertical bob is 1-2 px by design (animation.md says
    # exactly 1). More than 3 means the character is sinking or rising in
    # frame -- feet leave the floor line, which reads as floating.
    "bbox_drift_y":     {"op": "le", "value": 3, "hard": True},
}


def _luminance(rgb):
    return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]


def _opaque_rgb(img):
    for r, g, b, a in img.convert("RGBA").getdata():
        if a >= 128:
            yield (r, g, b)


# ---------------------------------------------------------------------------
# Single-sprite metrics
# ---------------------------------------------------------------------------


def alpha_crispness(img):
    """Fraction of alpha values that are exactly 0 or 255. 1.0 is clean.

    Overlaps qc_check.py's alpha_clean, but that one is pass/fail on the
    unique-value set. This grades HOW MUCH of the image is soft, which tells
    you whether you have a stray anti-aliased ring or one bad pixel.
    """
    alpha = img.convert("RGBA").split()[-1]
    data = list(alpha.getdata())
    if not data:
        return 1.0
    return sum(1 for a in data if a in (0, 255)) / len(data)


def outline_coverage(img):
    """Fraction of silhouette-edge pixels that sit in the darkest quartile.

    An "edge pixel" is opaque with at least one transparent 4-neighbour. If
    the sprite has a deliberate dark outline ring, nearly all of them will be
    dark; if it has none, the value collapses. Soft-gated -- outline-free
    styles are valid, so a low score is a question, not a verdict.

    Uses the image's own colors rather than a named palette, matching
    tileset.py's approach.
    """
    rgba = img.convert("RGBA")
    w, h = rgba.size
    px = rgba.load()

    colors = sorted(set(_opaque_rgb(rgba)), key=_luminance)
    if not colors:
        return 0.0
    dark_band = set(colors[: max(1, len(colors) // 4)])

    def transparent(x, y):
        if x < 0 or y < 0 or x >= w or y >= h:
            return True
        return px[x, y][3] < 128

    edge = dark = 0
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a < 128:
                continue
            if (transparent(x - 1, y) or transparent(x + 1, y)
                    or transparent(x, y - 1) or transparent(x, y + 1)):
                edge += 1
                if (r, g, b) in dark_band:
                    dark += 1
    return dark / edge if edge else 1.0


def baseline_alignment(img, min_contiguous=3):
    """True if the lowest opaque row has >= min_contiguous adjacent pixels.

    A sprite whose bottom row is a single stray pixel has no readable ground
    contact -- it will look like it is balancing on a point, and in a game it
    will not line up with the tile floor. Catches both stray specks and
    tiptoe poses.
    """
    rgba = img.convert("RGBA")
    w, h = rgba.size
    px = rgba.load()
    for y in range(h - 1, -1, -1):
        row = [px[x, y][3] >= 128 for x in range(w)]
        if any(row):
            run = best = 0
            for v in row:
                run = run + 1 if v else 0
                best = max(best, run)
            return best >= min_contiguous
    return False


def palette_size(img):
    return len(set(_opaque_rgb(img)))


def opaque_fraction(img):
    """Share of the canvas that is opaque. The precondition for every
    silhouette metric below.

    All the frame metrics assume the alpha channel isolates the CHARACTER. A
    fully-opaque frame has no silhouette at all -- "the subject" is then the
    whole rectangle, and IoU/bbox drift measure nothing. Above OPAQUE_LIMIT
    the frame gates are demoted to info rather than silently lying.

    This catches the easy case only, and the hard case is worth knowing
    about. This skill's own evals/eval-3-walk pair measures 0.68 opaque --
    it passes this check -- yet still scores IoU 0.70, in the same range as a
    deliberately sabotaged control. The reason is visible in an overlay: those
    frames kept the grey backdrop blob, the red VFX arc and the grass as
    opaque content, so the silhouette is a whole SCENE and what drifts
    between frames is scenery, not the character. No cheap metric separates
    "character pixels" from "scenery pixels", so nothing here tries to.

    Practical rule: a low silhouette_iou on frames that contain scenery is
    uninformative, not damning. Feed this isolated character sprites --
    transparent everywhere except the character -- or the number means
    nothing. Upstream ships no warning of any kind here.
    """
    alpha = img.convert("RGBA").getchannel("A")
    data = list(alpha.getdata())
    if not data:
        return 0.0
    return sum(1 for a in data if a >= 128) / len(data)


# Frames more opaque than this have no isolated subject to measure.
OPAQUE_LIMIT = 0.90


# ---------------------------------------------------------------------------
# Frame-to-frame metrics
# ---------------------------------------------------------------------------


def _mask(img):
    rgba = img.convert("RGBA")
    w, h = rgba.size
    px = rgba.load()
    return [[px[x, y][3] >= 128 for x in range(w)] for y in range(h)], w, h


def silhouette_iou(a, b):
    """Intersection-over-union of two frames' alpha silhouettes.

    The identity-drift detector. Two frames of the same character in
    different poses still overlap heavily (torso and head barely move); two
    frames where the model quietly redrew the character do not. A low value
    on a walk cycle means the edit passes lost the character, which is the
    exact failure mode sprite-sheets.md flags as untested past 2 frames.

    Sizes must match -- normalize frames first (slice_sheet.py does).
    """
    ma, wa, ha = _mask(a)
    mb, wb, hb = _mask(b)
    if (wa, ha) != (wb, hb):
        raise ValueError(f"frame size mismatch: {wa}x{ha} vs {wb}x{hb} -- "
                         "normalize frames to a common size first")
    inter = union = 0
    for y in range(ha):
        ra, rb = ma[y], mb[y]
        for x in range(wa):
            if ra[x] or rb[x]:
                union += 1
                if ra[x] and rb[x]:
                    inter += 1
    return inter / union if union else 1.0


def _bbox(img):
    bb = img.convert("RGBA").getchannel("A").point(
        lambda a: 255 if a >= 128 else 0).getbbox()
    return bb if bb else (0, 0, 0, 0)


def bbox_drift_xy(frames):
    """Max per-axis bounding-box drift across frames, vs frame 0.

    Returns (x_drift, y_drift). See the GATES notes for why they are graded
    very differently: horizontal spread is animation, vertical spread is
    usually a bug.
    """
    if len(frames) < 2:
        return 0, 0
    boxes = [_bbox(f) for f in frames]
    base = boxes[0]
    xd = yd = 0
    for bb in boxes[1:]:
        xd = max(xd, abs(bb[0] - base[0]), abs(bb[2] - base[2]))
        yd = max(yd, abs(bb[1] - base[1]), abs(bb[3] - base[3]))
    return xd, yd


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def _check(name, value):
    spec = GATES.get(name)
    if not spec:
        return None, "info"
    op, target = spec["op"], spec["value"]
    ok = {"eq": lambda: value == target,
          "ge": lambda: value >= target,
          "le": lambda: value <= target}[op]()
    return ok, "hard" if spec["hard"] else "soft"


def build_report(metrics, demote=()):
    """`demote` names are reported but never gated -- used when a metric's
    precondition does not hold, so it cannot honestly pass or fail."""
    out, hard, soft = {}, False, False
    for name, value in metrics.items():
        if name in demote:
            out[name] = {"value": value, "pass": None, "gate": "info",
                         "note": "not gated: precondition failed"}
            continue
        ok, kind = _check(name, value)
        out[name] = {"value": value, "pass": ok, "gate": kind}
        if ok is False:
            if kind == "hard":
                hard = True
            else:
                soft = True
    return {"metrics": out, "hard_fail": hard, "soft_fail": soft,
            "pass": not hard}


def print_report(title, report):
    status = "HARD-FAIL" if report["hard_fail"] else (
        "soft-fail" if report["soft_fail"] else "PASS")
    print(f"{status}: {title}")
    for name, e in report["metrics"].items():
        v = e["value"]
        vs = f"{v:.4f}" if isinstance(v, float) else str(v)
        mark = "ok  " if e["pass"] else ("FAIL" if e["pass"] is False else "--  ")
        print(f"  {mark} {name:<20} {vs:>10}  ({e['gate']})")
    if report.get("warning"):
        print(f"  ! {report['warning']}")


SILHOUETTE_METRICS = ("outline_coverage", "baseline_alignment",
                      "silhouette_iou", "bbox_drift_x", "bbox_drift_y")


def evaluate_sprite(img):
    opaque = opaque_fraction(img)
    demote = SILHOUETTE_METRICS if opaque > OPAQUE_LIMIT else ()
    report = build_report({
        "alpha_crispness": alpha_crispness(img),
        "outline_coverage": outline_coverage(img),
        "baseline_alignment": baseline_alignment(img),
        "opaque_fraction": opaque,
        "palette_size": palette_size(img),
    }, demote=demote)
    if demote:
        report["warning"] = (
            f"opaque_fraction {opaque:.2f} > {OPAQUE_LIMIT} -- background not "
            "removed, so silhouette metrics measure the canvas, not the "
            "subject. Not gated. Run comfy_rmbg.py or pixelize.py --alpha first."
        )
    return report


def evaluate_frames(frames):
    # Compare frame 0 against the frame half a cycle away -- on a 4-frame walk
    # that is frame 2, the mirrored contact pose, which is the most different
    # the silhouette should ever legitimately get. Comparing adjacent frames
    # would be too easy a test to fail.
    far = frames[len(frames) // 2] if len(frames) > 2 else frames[-1]
    xd, yd = bbox_drift_xy(frames)
    opaque = max(opaque_fraction(f) for f in frames)
    demote = SILHOUETTE_METRICS if opaque > OPAQUE_LIMIT else ()
    report = build_report({
        "silhouette_iou": silhouette_iou(frames[0], far),
        "bbox_drift_x": xd,
        "bbox_drift_y": yd,
        "alpha_crispness": min(alpha_crispness(f) for f in frames),
        "opaque_fraction": opaque,
        "frame_count": len(frames),
    }, demote=demote)
    if demote:
        report["warning"] = (
            f"opaque_fraction {opaque:.2f} > {OPAQUE_LIMIT} -- these frames "
            "still have their background, so silhouette_iou and bbox_drift "
            "score background/VFX movement, not character drift. Not gated. "
            "Remove the background, then re-run."
        )
    return report


def _write(report, path):
    Path(path).write_text(json.dumps(report, indent=2))
    print(f"  -> {Path(path).name}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("sprite", help="art metrics for one sprite")
    p.add_argument("image")

    p = sub.add_parser("frames", help="consistency across separate frame files")
    p.add_argument("images", nargs="+")

    p = sub.add_parser("sheet", help="consistency across a horizontally packed sheet")
    p.add_argument("image")
    p.add_argument("--tile-size", type=int, required=True)
    p.add_argument("--frames", type=int, required=True)

    args = ap.parse_args()

    if args.cmd == "sprite":
        img = Image.open(args.image).convert("RGBA")
        report = evaluate_sprite(img)
        print_report(Path(args.image).name, report)
        _write(report, Path(args.image).with_name(
            Path(args.image).stem + "_artqc.json"))

    elif args.cmd == "frames":
        if len(args.images) < 2:
            print("need at least 2 frames", file=sys.stderr)
            sys.exit(2)
        frames = [Image.open(p).convert("RGBA") for p in args.images]
        try:
            report = evaluate_frames(frames)
        except ValueError as exc:
            print(f"art_qc: {exc}", file=sys.stderr)
            sys.exit(2)
        print_report(f"{len(frames)} frames", report)
        _write(report, Path(args.images[0]).with_name("frames_artqc.json"))

    else:
        sheet = Image.open(args.image).convert("RGBA")
        ts = args.tile_size
        frames = [sheet.crop((i * ts, 0, (i + 1) * ts, ts)) for i in range(args.frames)]
        report = evaluate_frames(frames)
        print_report(Path(args.image).name, report)
        _write(report, Path(args.image).with_name(
            Path(args.image).stem + "_artqc.json"))

    sys.exit(0 if report["pass"] else 1)


if __name__ == "__main__":
    main()
