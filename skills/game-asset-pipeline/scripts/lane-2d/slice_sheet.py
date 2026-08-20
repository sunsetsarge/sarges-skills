"""Project Blackpaw asset slicer.

Handles three sheet families found in C:\\Terrorier:
  * bordered grids (gates/props/hazards)  - thin ruled cell borders
  * labelled character sheets (enemies)   - whitespace gaps + left text column
  * sectioned character sheets (player)   - bordered cells grouped in sections
plus stage layers (no slicing) and weather sheets (black matte, screen blend).

Strategy: key the matte, delete long thin ruled lines geometrically, run
connected components, cluster components into frames, and reject text labels
by relative size. Every result is written as a contact sheet for visual QA.
"""
import os, sys, json
import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = r"C:\Terrorier"
OUT = os.path.join(ROOT, "sliced")
QA = os.path.join(ROOT, "qa")


def load(path):
    return np.asarray(Image.open(path).convert("RGB")).astype(np.int16)


def matte_of(a):
    """Sample the four corners to find the background colour."""
    h, w, _ = a.shape
    s = np.concatenate([
        a[0:10, 0:10].reshape(-1, 3), a[0:10, -10:].reshape(-1, 3),
        a[-10:, 0:10].reshape(-1, 3), a[-10:, -10:].reshape(-1, 3)])
    return np.median(s, axis=0)


def fg_mask(a, matte, thresh=60):
    return np.abs(a - matte).sum(2) > thresh


def strip_rules(fg, min_len_frac=0.30, max_thick=7):
    """Remove ruled border lines: long runs that are only a few pixels thick."""
    h, w = fg.shape
    out = fg.copy()
    # horizontal rules
    cov = fg.sum(1)
    for y in np.where(cov > w * min_len_frac)[0]:
        y0 = y
        while y0 > 0 and fg[y0 - 1].sum() > w * min_len_frac:
            y0 -= 1
        if y - y0 < max_thick:
            out[y, :] = False
    # vertical rules
    cov = fg.sum(0)
    for x in np.where(cov > h * min_len_frac)[0]:
        x0 = x
        while x0 > 0 and fg[:, x0 - 1].sum() > h * min_len_frac:
            x0 -= 1
        if x - x0 < max_thick:
            out[:, x] = False
    return out


def components(fg, min_px=120):
    lab, n = ndimage.label(fg, structure=np.ones((3, 3)))
    boxes = []
    for i, sl in enumerate(ndimage.find_objects(lab), start=1):
        ys, xs = sl
        area = int((lab[sl] == i).sum())
        if area < min_px:
            continue
        boxes.append([xs.start, ys.start, xs.stop, ys.stop, area])
    return boxes


def projection_bands(fg, min_gap=10, min_rows=14):
    """Find horizontal bands from a row-coverage projection.

    Far more stable than clustering components: animation rows are separated by
    genuine whitespace, so the projection has unambiguous zero runs.
    """
    cov = fg.sum(1)
    on = cov > 0
    bands = []
    s = None
    for i, v in enumerate(on):
        if v and s is None:
            s = i
        elif not v and s is not None:
            bands.append([s, i]); s = None
    if s is not None:
        bands.append([s, len(on)])
    # stitch bands separated by a hairline gap (antialiasing, thin limbs)
    merged = []
    for b in bands:
        if merged and b[0] - merged[-1][1] < min_gap:
            merged[-1][1] = b[1]
        else:
            merged.append(b)
    return [b for b in merged if b[1] - b[0] >= min_rows]


def band_rows(boxes, fg, zone_x0=0, min_gap=10, min_rows=14):
    """Assign components to projection bands by their centre y."""
    bands = projection_bands(fg, min_gap=min_gap, min_rows=min_rows)
    out = [[] for _ in bands]
    for b in boxes:
        cy = (b[1] + b[3]) / 2
        for i, (y0, y1) in enumerate(bands):
            if y0 <= cy < y1:
                out[i].append(b); break
    return [sorted(band, key=lambda b: b[0]) for band in out if band]


def remove_text(a, fg, min_ratio=0.34):
    """Zero out caption text before banding.

    Captions are near-black, desaturated and far shorter than the artwork, so a
    height test plus a colour test separates them from sprites reliably. Doing
    this on the mask (not on frames) stops labels being merged into frame 0.
    """
    lab, n = ndimage.label(fg, structure=np.ones((3, 3)))
    objs = ndimage.find_objects(lab)
    heights = [sl[0].stop - sl[0].start for sl in objs if sl]
    if not heights:
        return fg
    med = float(np.median(heights))
    out = fg.copy()
    killed = 0
    for i, sl in enumerate(objs, start=1):
        if sl is None:
            continue
        hh = sl[0].stop - sl[0].start
        if hh >= min_ratio * med:
            continue
        sel = lab[sl] == i
        px = a[sl][sel]
        if px.size == 0:
            continue
        dark = (px.max(1) < 90).mean()
        sat = float(np.mean(px.max(1) - px.min(1)))
        if dark > 0.75 and sat < 42:
            out[sl][sel] = False
            killed += 1
    return out


def cluster_frames(band, fg, gap):
    """Split a band into frames using its own column-coverage projection.

    Sheets separate frames with real whitespace, so a projection is exact where
    component-gap clustering fuses neighbours or splits detached weapons.
    """
    if not band:
        return []
    y0 = min(b[1] for b in band); y1 = max(b[3] for b in band)
    x0 = min(b[0] for b in band); x1 = max(b[2] for b in band)
    cov = fg[y0:y1, x0:x1].sum(0) > 0
    runs = []
    s = None
    for i, v in enumerate(cov):
        if v and s is None:
            s = i
        elif not v and s is not None:
            runs.append([s, i]); s = None
    if s is not None:
        runs.append([s, len(cov)])
    merged = []
    for r in runs:
        if merged and r[0] - merged[-1][1] < gap:
            merged[-1][1] = r[1]
        else:
            merged.append(r)
    frames = []
    for rx0, rx1 in merged:
        ax0, ax1 = x0 + rx0, x0 + rx1
        sub = fg[y0:y1, ax0:ax1]
        rowsy = np.where(sub.any(1))[0]
        if rowsy.size == 0:
            continue
        frames.append([ax0, y0 + int(rowsy[0]), ax1, y0 + int(rowsy[-1]) + 1])
    return frames


def find_rules(fg, axis, frac=0.55, max_thick=8):
    """Return centre positions of thin ruled lines along an axis."""
    n = fg.shape[1] if axis == 0 else fg.shape[0]
    cov = fg.sum(1 - axis) if axis == 0 else fg.sum(0)
    hits = np.where(cov > n * frac)[0]
    groups = []
    for i in hits:
        if groups and i - groups[-1][-1] <= 2:
            groups[-1].append(i)
        else:
            groups.append([i])
    return [int(np.mean(g)) for g in groups if len(g) <= max_thick]


def slice_grid(a, fg, zone, frac=0.94):
    """Exact cell extraction for ruled sheets.

    Horizontal rules define row bands; vertical rules are then found *within*
    each band, so sections whose columns do not line up globally still slice
    correctly. Returns rows of content bounding boxes.
    """
    x0, x1 = zone
    sub = fg[:, x0:x1]
    hr = find_rules(sub, 0, frac)
    if len(hr) < 2:
        return []
    rows = []
    for top, bot in zip(hr, hr[1:]):
        if bot - top < 24:
            continue
        band = sub[top + 2:bot - 1]
        if not band.any():
            continue
        vr = find_rules(band, 1, frac)
        edges = [0] + vr + [band.shape[1]]
        edges = sorted(set(edges))
        cells = []
        for l, r in zip(edges, edges[1:]):
            if r - l < 16:
                continue
            cell = band[:, l + 1:r - 1]
            ys, xs = np.where(cell)
            if ys.size < 80:
                continue
            cells.append([x0 + l + 1 + int(xs.min()), top + 2 + int(ys.min()),
                          x0 + l + 1 + int(xs.max()) + 1, top + 2 + int(ys.max()) + 1])
        if cells:
            rows.append(cells)
    return rows


def keyed_rgba(a, matte, box, soft=28):
    """Crop and build an alpha channel from distance to the matte."""
    x0, y0, x1, y1 = box
    sub = a[y0:y1, x0:x1].astype(np.float32)
    d = np.abs(sub - matte).sum(2)
    alpha = np.clip((d - soft) / 70.0, 0, 1)
    # de-fringe: pull matte colour out of semi-transparent edge pixels
    with np.errstate(invalid="ignore", divide="ignore"):
        rgb = (sub - matte * (1 - alpha)[..., None]) / np.maximum(alpha, 1e-3)[..., None]
    rgb = np.clip(np.where(alpha[..., None] > 0.02, rgb, sub), 0, 255)
    out = np.dstack([rgb, alpha * 255]).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


def trim(im):
    bb = im.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
    return im.crop(bb) if bb else im


def slice_sheet(path, name, gap=18, min_px=120, label_reject=0.45, thresh=60,
                zones=None, mode="gaps", band_gap=10, band_min=14, grid_frac=0.94):
    a = load(path)
    matte = matte_of(a)
    raw_fg = fg_mask(a, matte, thresh)          # rules still present
    full_fg = remove_text(a, strip_rules(raw_fg))  # content only
    h, w = full_fg.shape
    # zones let a multi-column sheet be segmented one column at a time
    spans = zones or [[0, w]]
    rows = []
    if mode == "auto":
        # ruled sheets show several full-width hairlines; unruled ones show none
        mode = "grid" if len(find_rules(raw_fg, 0, 0.94)) >= 3 else "gaps"
    if mode == "grid":
        for span in spans:
            rows.extend(slice_grid(a, raw_fg, span, frac=grid_frac))
        # re-crop each cell against the text-free mask so captions are excluded
        clean = []
        for r in rows:
            cells = []
            for x0, y0, x1, y1 in r:
                # inset kills leftover cell-border stubs before measuring content
                ix0, iy0 = x0 + 3, y0 + 3
                sub = full_fg[iy0:y1 - 3, ix0:x1 - 3]
                if sub.size == 0:
                    continue
                ys, xs = np.where(sub)
                if ys.size < 80:
                    continue
                cells.append([ix0 + int(xs.min()), iy0 + int(ys.min()),
                              ix0 + int(xs.max()) + 1, iy0 + int(ys.max()) + 1])
            if cells:
                clean.append(cells)
        rows = clean
    for x0, x1 in (spans if mode != "grid" else []):
        fg = full_fg[:, x0:x1]
        boxes = [[b[0] + x0, b[1], b[2] + x0, b[3], b[4]]
                 for b in components(fg, min_px)]
        if not boxes:
            continue
        for band in band_rows(boxes, fg, min_gap=band_gap, min_rows=band_min):
            frames = cluster_frames(band, full_fg, gap)
            if not frames:
                continue
            # reject labels: much shorter than the tallest frame in the band
            tall = max(f[3] - f[1] for f in frames)
            frames = [f for f in frames
                      if (f[3] - f[1]) >= label_reject * tall and (f[2] - f[0]) > 12]
            if frames:
                rows.append(frames)
    if not rows:
        return {"name": name, "error": "no frames"}
    # global size filter: kills leftover caption text that owned its own band
    areas = [(f[2] - f[0]) * (f[3] - f[1]) for r in rows for f in r]
    floor = 0.12 * float(np.median(areas))
    rows = [[f for f in r if (f[2] - f[0]) * (f[3] - f[1]) >= floor] for r in rows]
    rows = [r for r in rows if r]

    def is_caption(box):
        """Big bold section headings survive the mask pre-pass; kill them here."""
        x0, y0, x1, y1 = box
        sel = full_fg[y0:y1, x0:x1]
        if sel.size == 0 or not sel.any():
            return True
        px = a[y0:y1, x0:x1][sel]
        fill = sel.mean()
        dark = (px.max(1) < 90).mean()
        sat = float(np.mean(px.max(1) - px.min(1)))
        return fill < 0.42 and dark > 0.80 and sat < 45

    rows = [[f for f in r if not is_caption(f)] for r in rows]
    rows = [r for r in rows if r]
    outdir = os.path.join(OUT, name)
    os.makedirs(outdir, exist_ok=True)
    meta = {"name": name, "source": path, "matte": [int(v) for v in matte], "rows": []}
    for ri, row in enumerate(rows):
        entry = []
        for fi, box in enumerate(row):
            im = trim(keyed_rgba(a, matte, box))
            fn = f"r{ri}_f{fi}.png"
            im.save(os.path.join(outdir, fn))
            entry.append({"file": fn, "box": box, "size": list(im.size)})
        meta["rows"].append(entry)
    with open(os.path.join(outdir, "meta.json"), "w") as f:
        json.dump(meta, f, indent=1)
    return meta


def contact_sheet(name, cell=132, pad=6):
    """Render every sliced frame on a checkerboard so alpha errors are visible."""
    outdir = os.path.join(OUT, name)
    meta = json.load(open(os.path.join(outdir, "meta.json")))
    rows = meta["rows"]
    if not rows:
        return None
    cols = max(len(r) for r in rows)
    W = cols * (cell + pad) + pad
    H = len(rows) * (cell + pad) + pad
    bg = Image.new("RGB", (W, H), (40, 44, 52))
    ck = Image.new("RGB", (cell, cell), (70, 74, 84))
    for yy in range(0, cell, 16):
        for xx in range(0, cell, 16):
            if (xx // 16 + yy // 16) % 2 == 0:
                ck.paste((92, 96, 108), (xx, yy, min(xx + 16, cell), min(yy + 16, cell)))
    for ri, row in enumerate(rows):
        for fi, fr in enumerate(row):
            im = Image.open(os.path.join(outdir, fr["file"])).convert("RGBA")
            im.thumbnail((cell, cell))
            x = pad + fi * (cell + pad); y = pad + ri * (cell + pad)
            bg.paste(ck, (x, y))
            bg.paste(im, (x + (cell - im.size[0]) // 2, y + (cell - im.size[1]) // 2), im)
    p = os.path.join(QA, f"contact_{name}.png")
    bg.save(p)
    return p


if __name__ == "__main__":
    jobs = json.load(open(sys.argv[1]))
    report = []
    for j in jobs:
        m = slice_sheet(ROOT + "\\" + j["src"], j["name"],
                        gap=j.get("gap", 18), min_px=j.get("min_px", 120),
                        label_reject=j.get("label_reject", 0.45),
                        thresh=j.get("thresh", 60), zones=j.get("zones"),
                        mode=j.get("mode", "gaps"),
                        band_gap=j.get("band_gap", 10), band_min=j.get("band_min", 14),
                        grid_frac=j.get("grid_frac", 0.94))
        if "error" in m:
            report.append(f"{j['name']}: ERROR {m['error']}")
            continue
        c = contact_sheet(j["name"])
        counts = [len(r) for r in m["rows"]]
        report.append(f"{j['name']}: rows={len(counts)} frames={counts} -> {c}")
    print("\n".join(report))
