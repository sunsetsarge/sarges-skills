"""Seamless-tile toolkit + Tiled (mapeditor.org) export.

Fills the gap the skill's own description has always claimed ("tiles",
"a tileset") but never had code for. Two jobs:

  1. MEASURE and FIX tileability. `seam_diff` scores how badly a tile's
     opposite edges disagree when wrapped -- the number behind the manual
     "shift by half and eyeball it" check in references/patterns.md. Three
     escalating fix strategies, auto-selected by whichever scores best.
  2. EXPORT a packed tile sheet as Tiled TSX (+ a demo TMJ map). references/
     export.md covers Aseprite/Unity/Godot/Phaser spritesheets -- those are
     *animation* formats. A tilemap editor needs a tileset definition, which
     is a different file, and Tiled's is the de-facto standard.

Ported from ianlintner/ai-pixel-art-image-generation (MIT) -- see
THIRD-PARTY.md. One deliberate divergence from upstream: upstream re-quantizes
blended pixels against a *named* palette (DB32, PICO-8...), which forces the
whole pipeline onto fixed palettes. This version snaps to the colors already
present in the input image instead, so it composes with unfake's adaptive
per-image palettes (Lane A/B/C) AND with Lane D's presets without either side
having to know about the other.

Pure Pillow, no numpy/torch -- runs on the base interpreter
(C:\\AI-Shared\\python.exe), not the venvs.

Usage:
  # score a single tile (exit 0 = passes the gate)
  python tileset.py seam grass.png

  # fix it, writing grass_seamless.png
  python tileset.py fix grass.png -o grass_seamless.png [--strategy auto]

  # score every tile in a packed sheet
  python tileset.py sheet overworld.png --tile-size 32 --columns 8

  # emit overworld.tsx + overworld.tmj next to the sheet
  python tileset.py export overworld.png --tile-size 32 --columns 8 \\
      --name overworld --names grass,dirt,water,stone
"""
import argparse
import json
import math
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image

# Mean per-edge-pixel L2 RGB distance, on a 0-255 scale. Upstream's value.
# Empirically: a genuinely tiling texture lands in the low single digits; a
# framed "one object on a background" image scores 40+. 12.0 sits in the dead
# zone between them, so it separates the two cases rather than finely grading
# either. Re-tune per art style rather than treating it as a constant.
DEFAULT_SEAM_THRESHOLD = 12.0

STRATEGIES = ("none", "torus", "edge_match", "auto")


# ---------------------------------------------------------------------------
# Measurement
# ---------------------------------------------------------------------------


def seam_diff(img):
    """Mean L2 RGB distance between wrap-adjacent edges. Lower is better.

    Compares column 0 against column w-1 and row 0 against row h-1 -- i.e.
    exactly the pixels that end up side by side when the tile is laid next to
    a copy of itself. Alpha is ignored; a tile with transparent edges scores
    on whatever RGB sits under the transparency, so score opaque tiles.
    """
    rgba = img.convert("RGBA")
    w, h = rgba.size
    px = rgba.load()

    def d(a, b):
        return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)

    total = 0.0
    for y in range(h):
        total += d(px[0, y], px[w - 1, y])
    for x in range(w):
        total += d(px[x, 0], px[x, h - 1])
    count = w + h
    return total / count if count else 0.0


def color_set(img):
    """Every distinct opaque RGB in the image -- this image's actual palette."""
    rgba = img.convert("RGBA")
    out = set()
    for r, g, b, a in rgba.getdata():
        if a >= 128:
            out.add((r, g, b))
    return out


def _snap_to_colors(img, colors):
    """Force every pixel onto the nearest color in `colors` (squared-L2).

    Replaces upstream's `quantize(palette=named_palette)`. Blending creates
    in-between colors that pixel art must not keep -- this puts them back on
    the art's own ramp instead of on some external palette's. Memoized, since
    a blended tile only ever contains a few hundred distinct colors.
    """
    if not colors:
        return img
    palette = list(colors)
    rgba = img.convert("RGBA")
    px = rgba.load()
    w, h = rgba.size
    cache = {}
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            key = (r, g, b)
            if key in cache:
                best = cache[key]
            elif key in colors:
                best = key
                cache[key] = best
            else:
                best = min(
                    palette,
                    key=lambda c: (c[0] - r) ** 2 + (c[1] - g) ** 2 + (c[2] - b) ** 2,
                )
                cache[key] = best
            px[x, y] = (best[0], best[1], best[2], a)
    return rgba


# ---------------------------------------------------------------------------
# Fix strategies
# ---------------------------------------------------------------------------


def _roll(img, dx, dy):
    """Wrap-shift an image by (dx, dy). Same idea as Sprite.shift(wrap=True)."""
    w, h = img.size
    dx %= w
    dy %= h
    if dx == 0 and dy == 0:
        return img.copy()
    out = Image.new(img.mode, img.size)
    out.paste(img, (dx, dy))
    if dx:
        out.paste(img.crop((w - dx, 0, w, h)), (0, dy))
    if dy:
        out.paste(img.crop((0, h - dy, w, h)), (dx, 0))
    if dx and dy:
        out.paste(img.crop((w - dx, h - dy, w, h)), (0, 0))
    return out


def crop_center(img, tile_size):
    """Center tile_size x tile_size crop.

    The cheapest tileability trick and the one to prefer: generate the texture
    at 3x the tile size and keep the middle. The center of a large continuous
    surface has no frame, no vignette and no subject -- it is *structurally*
    closer to tiling than any amount of post-hoc blending can make a framed
    image. Blending is damage control; this is prevention.
    """
    w, h = img.size
    left = (w - tile_size) // 2
    top = (h - tile_size) // 2
    return img.crop((left, top, left + tile_size, top + tile_size))


def torus_blend(img, feather=2):
    """Roll 50%, feather the resulting center cross, roll back, re-snap.

    Moves the seam into the middle of the image where it can be blended
    against real neighbouring content, then returns it to the edge. Gentle --
    it preserves content but does not guarantee the edges actually match.
    """
    rgba = img.convert("RGBA")
    w, h = rgba.size
    colors = color_set(rgba)
    dx, dy = w // 2, h // 2

    rolled = _roll(rgba, dx, dy)
    px = rolled.load()
    denom = feather * 2 + 2

    for x in range(w):
        for yo in range(-feather, feather + 1):
            y = dy + yo
            if 0 <= y < h:
                y_other = (y + (-1 if yo > 0 else 1)) % h
                src = px[x, y_other]
                dst = px[x, y]
                t = 0.5 - abs(yo) / denom
                px[x, y] = (
                    int(dst[0] * (1 - t) + src[0] * t),
                    int(dst[1] * (1 - t) + src[1] * t),
                    int(dst[2] * (1 - t) + src[2] * t),
                    dst[3],
                )
    for y in range(h):
        for xo in range(-feather, feather + 1):
            x = dx + xo
            if 0 <= x < w:
                x_other = (x + (-1 if xo > 0 else 1)) % w
                src = px[x_other, y]
                dst = px[x, y]
                t = 0.5 - abs(xo) / denom
                px[x, y] = (
                    int(dst[0] * (1 - t) + src[0] * t),
                    int(dst[1] * (1 - t) + src[1] * t),
                    int(dst[2] * (1 - t) + src[2] * t),
                    dst[3],
                )

    return _snap_to_colors(_roll(rolled, -dx, -dy), colors)


def edge_match_blend(img, blend_width=None):
    """Force opposite edges equal by averaging, then fade back inward.

    Guarantees a low seam score because it makes the edges identical by
    construction. The cost is real: it overwrites up to blend_width px of
    actual artwork on all four sides with an average. On a busy tile that
    reads as a smeared border. Use it as the last resort `auto` treats it as,
    and look at the result -- this is the one strategy that can pass the gate
    while looking worse.
    """
    rgba = img.convert("RGBA")
    w, h = rgba.size
    colors = color_set(rgba)
    if blend_width is None:
        blend_width = max(2, min(w, h) // 8)
    blend_width = max(1, min(blend_width, w // 2, h // 2))
    px = rgba.load()

    for y in range(h):
        left = px[0, y]
        right = px[w - 1, y]
        avg = ((left[0] + right[0]) // 2, (left[1] + right[1]) // 2, (left[2] + right[2]) // 2)
        for k in range(blend_width):
            t = 1.0 - (k / blend_width)
            for x in (k, w - 1 - k):
                src = px[x, y]
                px[x, y] = (
                    int(src[0] * (1 - t) + avg[0] * t),
                    int(src[1] * (1 - t) + avg[1] * t),
                    int(src[2] * (1 - t) + avg[2] * t),
                    src[3],
                )

    for x in range(w):
        top = px[x, 0]
        bot = px[x, h - 1]
        avg = ((top[0] + bot[0]) // 2, (top[1] + bot[1]) // 2, (top[2] + bot[2]) // 2)
        for k in range(blend_width):
            t = 1.0 - (k / blend_width)
            for y in (k, h - 1 - k):
                src = px[x, y]
                px[x, y] = (
                    int(src[0] * (1 - t) + avg[0] * t),
                    int(src[1] * (1 - t) + avg[1] * t),
                    int(src[2] * (1 - t) + avg[2] * t),
                    src[3],
                )

    return _snap_to_colors(rgba, colors)


def make_seamless(img, strategy="auto", threshold=DEFAULT_SEAM_THRESHOLD):
    """Apply a strategy, return (image, metrics).

    'auto' short-circuits if the tile already passes, then tries torus, then
    edge_match, and returns whichever scored lowest -- including the original,
    so a strategy that makes things worse can never be returned.
    """
    before = seam_diff(img)
    metrics = {"seam_diff_before": round(before, 3), "threshold": threshold}

    if strategy == "none":
        metrics.update(strategy_used="none", seam_diff_after=round(before, 3))
        return img, metrics

    if strategy == "torus":
        out = torus_blend(img)
    elif strategy == "edge_match":
        out = edge_match_blend(img)
    elif strategy == "auto":
        if before <= threshold:
            metrics.update(
                strategy_used="none", seam_diff_after=round(before, 3),
                note="already within threshold, left untouched",
            )
            return img, metrics
        candidates = [("none", img, before)]
        t_img = torus_blend(img)
        candidates.append(("torus", t_img, seam_diff(t_img)))
        if candidates[-1][2] > threshold:
            e_img = edge_match_blend(img)
            candidates.append(("edge_match", e_img, seam_diff(e_img)))
        candidates.sort(key=lambda c: c[2])
        name, out, after = candidates[0]
        metrics.update(
            strategy_used=name,
            seam_diff_after=round(after, 3),
            tried={n: round(s, 3) for n, _, s in candidates},
        )
        metrics["pass"] = after <= threshold
        return out, metrics
    else:
        raise ValueError(f"Unknown strategy '{strategy}'. Valid: {STRATEGIES}")

    after = seam_diff(out)
    metrics.update(strategy_used=strategy, seam_diff_after=round(after, 3))
    metrics["pass"] = after <= threshold
    return out, metrics


def sheet_seam_diffs(sheet, tile_size, columns, tile_count=None):
    """Per-tile seam_diff for a packed sheet. Returns a list, tile order."""
    w, h = sheet.size
    rows = h // tile_size
    if tile_count is None:
        tile_count = columns * rows
    out = []
    for idx in range(tile_count):
        r, c = divmod(idx, columns)
        left, top = c * tile_size, r * tile_size
        if left + tile_size > w or top + tile_size > h:
            break
        out.append(seam_diff(sheet.crop((left, top, left + tile_size, top + tile_size))))
    return out


# ---------------------------------------------------------------------------
# Tiled export
# ---------------------------------------------------------------------------

TILED_VERSION = "1.10"
TILED_EDITOR_VERSION = "1.11.0"


def build_tsx(name, tile_size, columns, tile_count, image_filename,
              image_width, image_height, tile_names=None, animation=None):
    """Build a Tiled TSX ElementTree. Validates dims before emitting.

    Tiled silently renders garbage if the declared grid does not match the
    image, so the mismatch is raised here instead.
    """
    rows = (tile_count + columns - 1) // columns
    expected_w, expected_h = columns * tile_size, rows * tile_size
    if (image_width, image_height) != (expected_w, expected_h):
        raise ValueError(
            f"sheet is {image_width}x{image_height} but "
            f"columns={columns} x rows={rows} @ {tile_size}px needs "
            f"{expected_w}x{expected_h}"
        )

    el = ET.Element("tileset", {
        "version": TILED_VERSION,
        "tiledversion": TILED_EDITOR_VERSION,
        "name": name,
        "tilewidth": str(tile_size),
        "tileheight": str(tile_size),
        "tilecount": str(tile_count),
        "columns": str(columns),
        "spacing": "0",
        "margin": "0",
    })
    ET.SubElement(el, "image", {
        "source": image_filename,
        "width": str(image_width),
        "height": str(image_height),
    })

    tile_names = tile_names or {}
    for tid in range(tile_count):
        tname = tile_names.get(tid)
        has_anim = animation and tid == 0
        if not tname and not has_anim:
            continue
        tile_el = ET.SubElement(el, "tile", {"id": str(tid)})
        if tname:
            props = ET.SubElement(tile_el, "properties")
            ET.SubElement(props, "property", {"name": "name", "value": tname})
        if has_anim:
            anim_el = ET.SubElement(tile_el, "animation")
            for frame_id, duration in animation:
                ET.SubElement(anim_el, "frame",
                              {"tileid": str(frame_id), "duration": str(duration)})

    ET.indent(el, space="  ")
    return ET.ElementTree(el)


def build_tmj(tsx_filename, tile_size, map_w=10, map_h=10):
    """Minimal TMJ map referencing the external TSX, filled with tile 1.

    TMJ layer data is firstgid-offset, so the first tile in the set is 1, not
    0 -- writing 0 there means "empty" and produces a blank map.
    """
    return {
        "compressionlevel": -1,
        "height": map_h,
        "infinite": False,
        "layers": [{
            "data": [1] * (map_w * map_h),
            "height": map_h, "width": map_w,
            "id": 1, "name": "Tile Layer 1",
            "opacity": 1, "type": "tilelayer", "visible": True, "x": 0, "y": 0,
        }],
        "nextlayerid": 2,
        "nextobjectid": 1,
        "orientation": "orthogonal",
        "renderorder": "right-down",
        "tiledversion": TILED_EDITOR_VERSION,
        "tileheight": tile_size,
        "tilewidth": tile_size,
        "tilesets": [{"firstgid": 1, "source": tsx_filename}],
        "type": "map",
        "version": TILED_VERSION,
        "width": map_w,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def cmd_seam(args):
    img = Image.open(args.image).convert("RGBA")
    score = seam_diff(img)
    ok = score <= args.threshold
    print(f"{'PASS' if ok else 'FAIL'}: {Path(args.image).name} "
          f"seam_diff={score:.3f} (threshold {args.threshold})")
    return 0 if ok else 1


def cmd_fix(args):
    src = Path(args.image)
    img = Image.open(src).convert("RGBA")
    if args.crop_center:
        img = crop_center(img, args.crop_center)
    out_img, metrics = make_seamless(img, args.strategy, args.threshold)
    out_path = Path(args.out) if args.out else src.with_name(f"{src.stem}_seamless.png")
    out_img.save(out_path)
    report = out_path.with_name(f"{out_path.stem}_seam.json")
    report.write_text(json.dumps(metrics, indent=2))
    print(f"tileset: {src.name} -> {out_path.name}  "
          f"seam {metrics['seam_diff_before']:.3f} -> {metrics['seam_diff_after']:.3f} "
          f"via {metrics['strategy_used']}")
    if metrics["strategy_used"] == "edge_match":
        print("  note: edge_match overwrites border pixels with an average -- "
              "look at the result before shipping it")
    return 0 if metrics.get("pass", metrics["seam_diff_after"] <= args.threshold) else 1


def cmd_sheet(args):
    sheet = Image.open(args.image).convert("RGBA")
    diffs = sheet_seam_diffs(sheet, args.tile_size, args.columns, args.tile_count)
    if not diffs:
        print("no tiles found -- check --tile-size/--columns against the image size",
              file=sys.stderr)
        return 2
    worst = max(range(len(diffs)), key=lambda i: diffs[i])
    mean = sum(diffs) / len(diffs)
    ok = mean <= args.threshold
    print(f"{'PASS' if ok else 'FAIL'}: {len(diffs)} tiles, "
          f"mean seam_diff={mean:.3f}, worst=tile {worst} ({diffs[worst]:.3f})")
    for i, d in enumerate(diffs):
        print(f"  tile {i:>3}: {d:8.3f} {'ok' if d <= args.threshold else 'FAIL'}")
    return 0 if ok else 1


def cmd_export(args):
    src = Path(args.image)
    sheet = Image.open(src)
    w, h = sheet.size
    columns = args.columns
    rows = h // args.tile_size
    tile_count = args.tile_count or (columns * rows)

    names = {}
    if args.names:
        for i, n in enumerate(args.names.split(",")):
            n = n.strip()
            if n:
                names[i] = n

    animation = None
    if args.animate_frames:
        animation = [(i, args.animate_duration) for i in range(args.animate_frames)]

    name = args.name or src.stem
    out_dir = Path(args.out_dir) if args.out_dir else src.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        tree = build_tsx(name, args.tile_size, columns, tile_count, src.name,
                         w, h, names, animation)
    except ValueError as exc:
        print(f"tileset: {exc}", file=sys.stderr)
        return 2
    tsx_path = out_dir / f"{name}.tsx"
    tree.write(tsx_path, encoding="UTF-8", xml_declaration=True)

    tmj_path = out_dir / f"{name}.tmj"
    tmj_path.write_text(json.dumps(
        build_tmj(tsx_path.name, args.tile_size, args.map_size, args.map_size), indent=2))

    print(f"tileset: {src.name} ({w}x{h}, {tile_count} tiles @ {args.tile_size}px) "
          f"-> {tsx_path.name} + {tmj_path.name}")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("seam", help="score one tile's seam continuity")
    p.add_argument("image")
    p.add_argument("--threshold", type=float, default=DEFAULT_SEAM_THRESHOLD)
    p.set_defaults(func=cmd_seam)

    p = sub.add_parser("fix", help="make a tile seamless")
    p.add_argument("image")
    p.add_argument("-o", "--out")
    p.add_argument("--strategy", choices=STRATEGIES, default="auto")
    p.add_argument("--threshold", type=float, default=DEFAULT_SEAM_THRESHOLD)
    p.add_argument("--crop-center", type=int, metavar="N",
                   help="first take the center NxN crop (use when the source was "
                        "generated at 3x tile size -- the preferred route)")
    p.set_defaults(func=cmd_fix)

    p = sub.add_parser("sheet", help="score every tile in a packed sheet")
    p.add_argument("image")
    p.add_argument("--tile-size", type=int, required=True)
    p.add_argument("--columns", type=int, required=True)
    p.add_argument("--tile-count", type=int)
    p.add_argument("--threshold", type=float, default=DEFAULT_SEAM_THRESHOLD)
    p.set_defaults(func=cmd_sheet)

    p = sub.add_parser("export", help="emit Tiled TSX + demo TMJ for a sheet")
    p.add_argument("image")
    p.add_argument("--tile-size", type=int, required=True)
    p.add_argument("--columns", type=int, required=True)
    p.add_argument("--tile-count", type=int)
    p.add_argument("--name", help="tileset name (default: image stem)")
    p.add_argument("--names", help="comma-separated per-tile names, in tile order")
    p.add_argument("--out-dir")
    p.add_argument("--map-size", type=int, default=10, help="demo TMJ map size in tiles")
    p.add_argument("--animate-frames", type=int,
                   help="declare tiles 0..N-1 as an animation on tile 0")
    p.add_argument("--animate-duration", type=int, default=120)
    p.set_defaults(func=cmd_export)

    args = ap.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
