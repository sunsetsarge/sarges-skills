"""Cut a generated sprite sheet (ChatGPT / DALL-E / Midjourney) into EQUAL cells
without ever cutting into a sprite.

Why not slice on a fixed grid: generated sheets are never on an exact grid. Sprites
drift, overlap the nominal cell lines, and carry glow or chips that stick out. Cutting
on lines clips them. This script finds the sprites first (connected artwork on a flat
matte), groups the pieces that belong together, then builds one cell size big enough
for the largest sprite and places every sprite in its own cell on a shared anchor.
A sprite can never be cropped, and every cell is the same size and shape, so frames
swap without shifting (spine rule 2: one shared box).

Grouping, in order of preference:
  --rows R --cols C   You know the layout. Each piece goes to the nominal grid cell
                      its centre falls in, so a sprite that crosses a grid line stays
                      whole. Best for clean ChatGPT sheets.
  (auto)              Rows from horizontal whitespace, then sprites from vertical
                      whitespace within each row (--gap sets the minimum gap).

Clean-up before grouping: ruled grid lines (long, thin, light) are removed, and
text labels ("IDLE", "WALK LEFT") are dropped: lines of three or more short,
mostly near-black glyphs side by side on one baseline, found before pieces are glued
together (labels often sit a few px above a sprite). Both
are reported in the manifest warnings, so check the contact sheet if art was dropped.

Matte: sampled from the corners (white, magenta, anything flat). Edges get soft alpha
and the matte colour is un-premultiplied out, so no halo on a dark game background.
Matte-coloured gaps inside a sprite become transparent when they reach the outline
(between chips, spikes) or are bigger than --keep-holes px (between an arm and a
weapon); small enclosed ones (eye whites) stay opaque.

Output (in OUT_DIR):
  <name>_<n>.<fmt>          one equal-size cell per sprite, n in reading order (1-based)
  <name>_<n>_piece_<k>      separate pieces of a --split cell (debris), trimmed
  <name>_atlas.<fmt>        all cells in one grid (with --atlas)
  <name>.json               manifest: cell size, scale, anchor, per-cell source boxes
  <name>_contact.png        QA sheet on a dark background, cell borders + numbers.
                            LOOK AT IT before using the output.

Examples:
  python cut_cells.py sheet.webp out/ --name chest_plate --rows 1 --cols 4 --split 4 --size 256
  python cut_cells.py walk.png out/ --name orc_walk --anchor bottom --size 192 --atlas
  python cut_cells.py icons.png out/ --rows 3 --cols 5 --square --size 128

Python 3.10 + Pillow + numpy + scipy (C:\\AI-Shared\\python.exe on Blaine's machine).
"""
import argparse, json, os, sys
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage


# ---------------------------------------------------------------- matte + mask

def matte_of(a):
    h, w, _ = a.shape
    k = max(4, min(h, w) // 50)
    s = np.concatenate([a[:k, :k].reshape(-1, 3), a[:k, -k:].reshape(-1, 3),
                        a[-k:, :k].reshape(-1, 3), a[-k:, -k:].reshape(-1, 3)])
    return np.median(s, axis=0)


def load(path, thresh):
    im = Image.open(path)
    if im.mode in ('RGBA', 'LA') and np.asarray(im.convert('RGBA'))[..., 3].min() < 250:
        rgba = np.asarray(im.convert('RGBA')).astype(np.float32)
        return rgba[..., :3], rgba[..., 3] > 16, None, rgba[..., 3] / 255.0
    a = np.asarray(im.convert('RGB')).astype(np.float32)
    matte = matte_of(a)
    dist = np.abs(a - matte).sum(2)
    return a, dist > thresh, matte, None


def strip_rules(fg, frac=0.3, max_thick=6):
    """Remove ruled grid lines: rows/columns mostly covered, in runs only a few px thick."""
    out, n = fg.copy(), 0
    for axis in (0, 1):
        cov = fg.sum(axis=1 - axis) > fg.shape[1 - axis] * frac
        for a, b in runs_of(cov, 1):
            if b - a <= max_thick:
                n += 1
                if axis == 0: out[a:b, :] = False
                else: out[:, a:b] = False
    return out, n


def remove_text(fg, rgb, max_h):
    """Drop label text: 3+ short, dark, colourless glyphs in a row on one baseline."""
    lab, n = ndimage.label(fg, structure=np.ones((3, 3)))
    glyphs = []
    for i, sl in enumerate(ndimage.find_objects(lab), start=1):
        ys, xs = sl
        h = ys.stop - ys.start
        if h > max_h or h < 4:
            continue
        own = lab[sl] == i
        px = rgb[sl][own]
        dark = (px.max(axis=1) < 130) & (px.max(axis=1) - px.min(axis=1) < 45)
        if dark.mean() > 0.5:
            glyphs.append((i, xs.start, xs.stop, ys.start, ys.stop))
    glyphs.sort(key=lambda g: g[1])          # left to right, so a word chains in reading order
    used, lines = set(), 0
    for a in glyphs:
        if a[0] in used:
            continue
        line = [a]
        for b in glyphs:
            if b[0] in used or b[1] <= line[-1][1]:
                continue
            last = line[-1]
            if abs((b[3] + b[4]) / 2 - (last[3] + last[4]) / 2) <= max(4, (last[4] - last[3]) * 0.4) and -3 <= b[1] - last[2] <= 24:
                line.append(b)
        h = max(g[4] - g[3] for g in line)
        span = line[-1][2] - line[0][1]
        # 3+ glyphs, or bold words whose letters run together into 1-2 wide blobs
        if len(line) >= 3 or span >= 2.2 * h:
            used.update(g[0] for g in line)
            lines += 1
    out = fg & ~np.isin(lab, list(used)) if used else fg
    return out, lines


def pieces_of(fg, rgb, min_area, join, text_h):
    """Connected artwork pieces. `join` px of closing glues glow/chips to their sprite."""
    m = ndimage.binary_closing(fg, iterations=join) if join else fg
    lab, n = ndimage.label(m, structure=np.ones((3, 3)))
    out, text = [], 0
    for i, sl in enumerate(ndimage.find_objects(lab), start=1):
        own = (lab[sl] == i) & fg[sl]
        area = int(own.sum())
        if area < min_area:
            continue
        ys, xs = sl
        if text_h and ys.stop - ys.start <= text_h and area < 1500:
            # leftover label fragment ("/", a word split off a line): short, small, dark
            px = rgb[sl][own]
            if ((px.max(axis=1) < 130) & (px.max(axis=1) - px.min(axis=1) < 45)).mean() > 0.55:
                text += 1
                continue
        out.append({'id': i, 'x0': xs.start, 'y0': ys.start, 'x1': xs.stop, 'y1': ys.stop, 'area': area,
                    'cx': (xs.start + xs.stop) / 2, 'cy': (ys.start + ys.stop) / 2})
    return lab, out, text


# ---------------------------------------------------------------- grouping

def runs_of(cov, min_gap):
    """Index runs where cov > 0, merging runs separated by fewer than min_gap empties."""
    runs, s, last = [], None, None
    for i, c in enumerate(list(cov) + [0]):
        if c and s is None:
            s = i if (last is None or i - last >= min_gap) else runs.pop()[0]
        if not c and s is not None:
            runs.append((s, i)); last = i; s = None
    return runs


def split_overlaps(lab, fg, pieces, rows, cols):
    """Grid mode only: a blob spanning well over one nominal cell is touching sprites
    (a club resting on the next body). Split it on the nominal cell lines; this is the
    one case where art is cut, because the sprites physically overlap in the source."""
    x0, y0, x1, y1 = bbox(pieces)
    cw, ch = (x1 - x0) / cols, (y1 - y0) / rows
    out, nxt, n_split = [], int(lab.max()) + 1, 0
    for p in pieces:
        if p['x1'] - p['x0'] <= 1.4 * cw and p['y1'] - p['y0'] <= 1.4 * ch:
            out.append(p); continue
        n_split += 1
        sl = (slice(p['y0'], p['y1']), slice(p['x0'], p['x1']))
        own = lab[sl] == p['id']
        yy, xx = np.mgrid[p['y0']:p['y1'], p['x0']:p['x1']]
        cell = np.clip(((yy - y0) // ch).astype(int), 0, rows - 1) * cols + np.clip(((xx - x0) // cw).astype(int), 0, cols - 1)
        for k in np.unique(cell[own]):
            m = own & (cell == k)
            if (m & fg[sl]).sum() < 60:
                continue
            lab[sl][m] = nxt
            ys, xs = np.where(m)
            q = {'id': nxt, 'x0': int(p['x0'] + xs.min()), 'y0': int(p['y0'] + ys.min()), 'x1': int(p['x0'] + xs.max() + 1),
                 'y1': int(p['y0'] + ys.max() + 1), 'area': int(m.sum())}
            q['cx'], q['cy'] = (q['x0'] + q['x1']) / 2, (q['y0'] + q['y1']) / 2
            out.append(q); nxt += 1
    return out, n_split


def group_grid(pieces, shape, rows, cols):
    # divide the area the artwork covers (labels already removed), not the whole sheet,
    # so a label margin or uneven border does not shift the grid
    x0, y0, x1, y1 = bbox(pieces)
    w, h = x1 - x0, y1 - y0
    cells = {}
    for p in pieces:
        r = max(0, min(rows - 1, int((p['cy'] - y0) / h * rows)))
        c = max(0, min(cols - 1, int((p['cx'] - x0) / w * cols)))
        cells.setdefault((r, c), []).append(p)
    return [((r, c), cells[(r, c)]) for r in range(rows) for c in range(cols) if (r, c) in cells]


def absorb_specks(groups, frac=0.3):
    """Fold groups much smaller than a row's typical sprite (a lone shard or spark
    that sits in its own gap) into the nearest sprite in the same row."""
    out = []
    for r in sorted({r for (r, _), _ in groups}):
        row = [list(g) for (rr, _), g in groups if rr == r]
        sizes = sorted(max(bbox(g)[2] - bbox(g)[0], bbox(g)[3] - bbox(g)[1]) for g in row)
        typical = sizes[len(sizes) // 2]
        keep = [g for g in row if max(bbox(g)[2] - bbox(g)[0], bbox(g)[3] - bbox(g)[1]) >= typical * frac]
        for g in row:
            if g in keep or not keep:
                continue
            cx = (bbox(g)[0] + bbox(g)[2]) / 2
            near = min(keep, key=lambda k: abs((bbox(k)[0] + bbox(k)[2]) / 2 - cx))
            near.extend(g)
        keep.sort(key=lambda g: bbox(g)[0])
        out += [((r, c), g) for c, g in enumerate(keep or row)]
    return out


def group_auto(pieces, fg, gap):
    groups = []
    for ri, (y0, y1) in enumerate(runs_of(fg.any(axis=1), gap)):
        band = [p for p in pieces if y0 <= p['cy'] < y1]
        cov = np.zeros(fg.shape[1], bool)
        for p in band:
            cov[p['x0']:p['x1']] = True
        for ci, (x0, x1) in enumerate(runs_of(cov, gap)):
            g = [p for p in band if x0 <= p['cx'] < x1]
            if g:
                groups.append(((ri, ci), g))
    return absorb_specks(groups)


# ---------------------------------------------------------------- cut-out

def cut(rgb, fg, lab, pieces, matte, alpha_in, soft_range, box, keep_holes=40):
    x0, y0, x1, y1 = box
    sub_lab = lab[y0:y1, x0:x1]
    own = np.isin(sub_lab, [p['id'] for p in pieces]) & fg[y0:y1, x0:x1]
    c = rgb[y0:y1, x0:x1].copy()
    if alpha_in is not None:
        a = np.where(own, alpha_in[y0:y1, x0:x1], 0.0)
        return Image.fromarray(np.dstack([c, a * 255]).clip(0, 255).astype(np.uint8), 'RGBA')
    filled = ndimage.binary_fill_holes(own)
    holes = filled & ~own
    # holes that reach the outline are gaps between chips: see-through. Deep holes stay.
    rim = filled & ~ndimage.binary_erosion(filled, iterations=8)
    hl, hn = ndimage.label(holes)
    if hn:
        touching = set(np.unique(hl[rim & holes]).tolist()) - {0}
        sizes = ndimage.sum(holes, hl, range(1, hn + 1))
        big = {i + 1 for i, a in enumerate(sizes) if a >= keep_holes}
        holes_open = np.isin(hl, list(touching | big))
        filled &= ~holes_open
    core = ndimage.binary_erosion(filled, iterations=2)
    dist = np.abs(c - matte).sum(2)
    soft = np.clip(dist / soft_range, 0, 1)
    a = np.where(core, 1.0, np.where(filled | ndimage.binary_dilation(own, iterations=1), soft, 0.0))
    aa = np.maximum(a, 1e-3)[..., None]
    c = np.where(a[..., None] < 1, (c - matte * (1 - aa)) / aa, c)
    return Image.fromarray(np.dstack([c, a * 255]).clip(0, 255).astype(np.uint8), 'RGBA')


def bbox(ps):
    return (min(p['x0'] for p in ps), min(p['y0'] for p in ps), max(p['x1'] for p in ps), max(p['y1'] for p in ps))


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('sheet'); ap.add_argument('out_dir')
    ap.add_argument('--name', help='output base name (default: sheet file name)')
    ap.add_argument('--rows', type=int); ap.add_argument('--cols', type=int)
    ap.add_argument('--anchor', choices=['center', 'bottom'], default='center',
                    help='center: sprite centres line up (parts, icons). bottom: feet line up (characters)')
    ap.add_argument('--square', action='store_true', help='square cells')
    ap.add_argument('--pad', type=int, default=6, help='free margin inside each cell, source px')
    ap.add_argument('--size', type=int, help='scale so the cell\'s longer side is this many px (downscale only)')
    ap.add_argument('--split', default='', help='comma list of cell numbers whose pieces are exported separately (debris)')
    ap.add_argument('--gap', type=int, default=6, help='auto mode: min whitespace between sprites, px')
    ap.add_argument('--join', type=int, default=3, help='px of closing that glues chips and glow to a sprite')
    ap.add_argument('--min-area', type=int, default=60, help='drop specks smaller than this (px)')
    ap.add_argument('--thresh', type=float, default=30, help='colour distance from the matte that counts as artwork')
    ap.add_argument('--soft', type=float, default=300, help='edge softness: matte distance (summed over RGB) at which an edge pixel is opaque')
    ap.add_argument('--text-h', type=int, default=40, help='max glyph height for label text removal (0 = keep text)')
    ap.add_argument('--keep-holes', type=int, default=40, help='enclosed matte holes smaller than this many px stay opaque')
    ap.add_argument('--format', choices=['webp', 'png'], default='webp')
    ap.add_argument('--atlas', action='store_true', help='also write all cells as one grid image')
    args = ap.parse_args()

    name = args.name or os.path.splitext(os.path.basename(args.sheet))[0]
    os.makedirs(args.out_dir, exist_ok=True)
    rgb, fg, matte, alpha_in = load(args.sheet, args.thresh)
    warnings = []
    fg, rules = strip_rules(fg)
    if rules:
        warnings.append(f'removed {rules} ruled grid line(s)')
    if args.text_h:
        fg, text = remove_text(fg, rgb, args.text_h)
        if text:
            warnings.append(f'dropped {text} line(s) of label text; use --text-h 0 to keep them')
    lab, pieces, frags = pieces_of(fg, rgb, args.min_area, args.join, args.text_h)
    if frags:
        warnings.append(f'dropped {frags} leftover label fragment(s)')
    if not pieces:
        sys.exit('no artwork found: check --thresh / the matte')
    if (args.rows is None) != (args.cols is None):
        sys.exit('give both --rows and --cols, or neither')
    if args.rows:
        pieces, n_split = split_overlaps(lab, fg, pieces, args.rows, args.cols)
        if n_split:
            warnings.append(f'{n_split} blob(s) of touching sprites were split on the grid lines: check those cells')
    groups = group_grid(pieces, fg.shape, args.rows, args.cols) if args.rows else group_auto(pieces, fg, args.gap)
    if not args.rows:  # number rows 0..n-1 over the rows that hold sprites
        order = {r: k for k, r in enumerate(sorted({r for (r, _), _ in groups}))}
        groups = [((order[r], c), g) for (r, c), g in groups]
    split = {int(s) for s in args.split.split(',') if s.strip()}

    cells_src = [g for i, g in enumerate(groups, 1) if i not in split]
    if not cells_src:
        sys.exit('every cell is split; nothing to size the cells from')
    bw = max(bbox(g)[2] - bbox(g)[0] for _, g in cells_src)
    bh = max(bbox(g)[3] - bbox(g)[1] for _, g in cells_src)
    cw, ch = bw + 2 * args.pad, bh + 2 * args.pad
    if args.square:
        cw = ch = max(cw, ch)
    cw += cw % 2; ch += ch % 2
    scale = min(1.0, args.size / max(cw, ch)) if args.size else 1.0
    ow, oh = round(cw * scale), round(ch * scale)

    H, W = fg.shape
    manifest = {'sheet': os.path.basename(args.sheet), 'matte': None if matte is None else [round(float(v)) for v in matte],
                'cell': {'w': ow, 'h': oh}, 'source_cell': {'w': cw, 'h': ch}, 'scale': round(scale, 6),
                'anchor': args.anchor, 'cells': [], 'pieces': []}
    tiles = []
    for n, ((r, c), g) in enumerate(groups, 1):
        x0, y0, x1, y1 = bbox(g)
        if x0 <= 1 or y0 <= 1 or x1 >= W - 1 or y1 >= H - 1:
            warnings.append(f'cell {n} touches the sheet edge: the source may already be cropped')
        if n in split:
            for k, p in enumerate(sorted(g, key=lambda p: (p['y0'], p['x0']))):
                im = cut(rgb, fg, lab, [p], matte, alpha_in, args.soft, (p['x0'], p['y0'], p['x1'], p['y1']), args.keep_holes)
                if scale < 1:
                    im = im.resize((max(1, round(im.width * scale)), max(1, round(im.height * scale))), Image.LANCZOS)
                f = f'{name}_{n}_piece_{k}.{args.format}'
                im.save(os.path.join(args.out_dir, f), quality=92, method=6) if args.format == 'webp' else im.save(os.path.join(args.out_dir, f))
                manifest['pieces'].append({'file': f, 'cell': n, 'w': im.width, 'h': im.height,
                                           'src': [p['x0'], p['y0'], p['x1'] - p['x0'], p['y1'] - p['y0']]})
            continue
        sprite = cut(rgb, fg, lab, g, matte, alpha_in, args.soft, (x0, y0, x1, y1), args.keep_holes)
        cell = Image.new('RGBA', (cw, ch), (0, 0, 0, 0))
        ox = (cw - sprite.width) // 2
        oy = (ch - sprite.height) // 2 if args.anchor == 'center' else ch - args.pad - sprite.height
        cell.alpha_composite(sprite, (ox, oy))
        if scale < 1:
            cell = cell.resize((ow, oh), Image.LANCZOS)
        f = f'{name}_{n}.{args.format}'
        cell.save(os.path.join(args.out_dir, f), quality=92, method=6) if args.format == 'webp' else cell.save(os.path.join(args.out_dir, f))
        manifest['cells'].append({'n': n, 'file': f, 'row': r, 'col': c, 'pieces': len(g),
                                  'src': [x0, y0, x1 - x0, y1 - y0],
                                  'sprite': [round(ox * scale, 2), round(oy * scale, 2), round(sprite.width * scale, 2), round(sprite.height * scale, 2)]})
        tiles.append((n, r, c, cell))

    widths = sorted(c['src'][2] for c in manifest['cells'])
    if widths and not args.rows and widths[-1] > 1.8 * widths[len(widths) // 2]:
        warnings.append(f'a cell is {widths[-1] / widths[len(widths) // 2]:.1f}x wider than typical: sprites that overlap '
                        'horizontally were merged; give --rows and --cols')
    rows_seen = sorted({r for _, r, _, _ in tiles})
    per_row = [sum(1 for t in tiles if t[1] == r) for r in rows_seen]
    if len(set(per_row)) > 1:
        warnings.append(f'rows hold different sprite counts {per_row}: check for merged or split sprites')
    if args.atlas and tiles:
        ncol = max(t[2] for t in tiles) + 1
        atlas = Image.new('RGBA', (ncol * ow, len(rows_seen) * oh), (0, 0, 0, 0))
        for n, r, c, im in tiles:
            atlas.alpha_composite(im, (c * ow, rows_seen.index(r) * oh))
        f = f'{name}_atlas.{args.format}'
        atlas.save(os.path.join(args.out_dir, f))
        manifest['atlas'] = {'file': f, 'cols': ncol, 'rows': len(rows_seen)}

    # contact sheet: dark background shows halos; borders show the cell; numbers match files
    per = 6
    k = min(1.0, 220 / max(ow, oh))
    tw, th = max(1, round(ow * k)), max(1, round(oh * k))
    cs = Image.new('RGB', (per * (tw + 10) + 10, (len(tiles) // per + 1) * (th + 26) + 10), (52, 54, 72))
    d = ImageDraw.Draw(cs)
    for i, (n, r, c, im) in enumerate(tiles):
        x, y = 10 + (i % per) * (tw + 10), 10 + (i // per) * (th + 26)
        cs.paste(im.resize((tw, th), Image.LANCZOS), (x, y), im.resize((tw, th), Image.LANCZOS))
        d.rectangle([x, y, x + tw - 1, y + th - 1], outline=(255, 210, 90))
        d.text((x + 2, y + th + 4), f'{n}  r{r} c{c}', fill=(230, 230, 240))
    cs.save(os.path.join(args.out_dir, f'{name}_contact.png'))

    manifest['warnings'] = warnings
    json.dump(manifest, open(os.path.join(args.out_dir, f'{name}.json'), 'w', newline='\n'), indent=2)
    print(f'{len(tiles)} cells of {ow}x{oh} (source {cw}x{ch}, scale {scale:.3f}), {len(manifest["pieces"])} pieces -> {args.out_dir}')
    for w in warnings:
        print('WARNING:', w)


if __name__ == '__main__':
    main()
