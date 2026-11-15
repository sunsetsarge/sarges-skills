"""Turn generated sprite art (a sheet or a folder of frames) into an Aseprite source file,
a packed RGBA sprite sheet and Aseprite's JSON sheet data, by running Aseprite headless.

Outputs (in OUT_DIR):
  <name>.aseprite   editable source: animation tags, frame timing, optional locked palette
  <name>.png        sprite sheet, always RGBA
  <name>.json       Aseprite sheet data: frames, meta.frameTags, meta.slices, meta.layers

Sits after cut_cells.py / slice_sheet.py in the 2D lane: those make equal cells, this
packs them. It never pads or resizes: frames of different sizes are an error.

Input:
  --sheet PNG --cell WxH | --grid COLSxROWS   equal-cell grid, read left to right, top to bottom
  --frames DIR_OR_GLOB                        PNGs in natural order (f_2 before f_10), equal size
  --key auto|RRGGBB|none                      exact colour -> fully transparent (auto = top-left pixel)
  --keep-empty                                keep sheet cells with no opaque pixel (dropped by default)

Tags (frame numbers are 1-based, counted over the KEPT frames in final order):
  --row-tags idle,walk,attack                 sheet input: one animation per sheet row
  --tags "run:1-6:pingpong:2,idle:7-8"        name:from-to[:direction[:repeats]]
  direction: forward (default) | reverse | pingpong | pingpong_reverse

Timing: --fps N (default 10) sets every frame to round(1000/N) ms; --tag-fps run=12,idle=4 overrides per tag.

Palette lock (the .aseprite is saved indexed, the exported PNG stays RGBA):
  --palette NAME_OR_PATH    .gpl .pal .hex .act .png .aseprite, or a bundled name (nes, gameboy, pico-8 ...)
  --max-colors N            derive an N-colour palette from the art instead
  --dither none|bayer2x2|bayer4x4|bayer8x8, --alpha-threshold 128 (alpha is made binary first)
  Index 0 is a transparent entry and the real colours start at 1, so transparency survives:
  the opaque-pixel count is checked before and after the lock.

Other: --pivot bottom-center|center|X,Y adds one slice "anchor" over the whole cell.
Export: --sheet-type packed|rows|columns|horizontal|vertical, --padding N (default 1),
  --extrude, --trim (per frame; the engine must then apply spriteSourceSize),
  --json-format array|hash.
Aseprite is found via --aseprite, env ASEPRITE_EXE, pixel-mcp config.json, the Steam
install, then PATH. It runs with ASEPRITE_USER_FOLDER pointing at a throwaway temp
folder so your real Aseprite settings are never touched (--keep-temp keeps it).

Every run verifies its own output (stats file, three files present, JSON frame count and
tags, RGBA sheet, palette membership and opaque-pixel count) and exits non-zero with
Aseprite's own output if anything is off.

Examples:
  python ase_pack.py out/ --name hero --sheet hero_sheet.png --cell 64x64 --key auto --row-tags idle,walk,attack --fps 8
  python ase_pack.py out/ --name hero --sheet hero_sheet.png --grid 8x4 --row-tags a,b,c,d --palette pico-8 --pivot bottom-center
  python ase_pack.py out/ --name run --frames cells/run_*.png --tags "run:1-6:pingpong" --tag-fps run=12
  python ase_pack.py --list-palettes

Python 3.10 + Pillow (C:\\AI-Shared\\python.exe on Blaine's machine).
"""
import argparse, glob, json, os, re, shutil, subprocess, sys, tempfile
from pathlib import Path
from PIL import Image, ImageChops

LUA = Path(__file__).resolve().parent / 'ase_pack.lua'
TIMEOUT = 60
DIRECTIONS = ('forward', 'reverse', 'pingpong', 'pingpong_reverse')
PALETTE_EXTS = ('.gpl', '.pal', '.hex', '.act', '.png', '.aseprite')
DITHERS = ('none', 'bayer2x2', 'bayer4x4', 'bayer8x8')
STEAM_EXE = r'C:\Program Files (x86)\Steam\steamapps\common\Aseprite\Aseprite.exe'


class Fail(Exception):
    """A user-facing error. `proc` (optional) is an Aseprite CompletedProcess to show."""
    def __init__(self, msg, proc=None):
        super().__init__(msg)
        self.proc = proc


def fwd(p):
    """Forward slashes: a backslash inside a Lua string is an escape."""
    return str(p).replace('\\', '/')


def natural_key(s):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', s)]


# ---------------------------------------------------------------- finding Aseprite

def find_aseprite(explicit):
    tried = []
    cands = []
    if explicit:
        cands.append(('--aseprite', explicit))
    if os.environ.get('ASEPRITE_EXE'):
        cands.append(('env ASEPRITE_EXE', os.environ['ASEPRITE_EXE']))
    cfg = Path.home() / '.config' / 'pixel-mcp' / 'config.json'
    try:
        p = json.loads(cfg.read_text(encoding='utf-8')).get('aseprite_path')
        if p:
            cands.append((f'aseprite_path in {cfg}', p))
    except (OSError, ValueError):
        pass
    cands.append(('Steam install', STEAM_EXE))
    for label, p in cands:
        tried.append(f'{label}: {p}')
        if os.path.isfile(p):
            return str(Path(p).resolve())
        if label == '--aseprite':
            raise Fail(f'--aseprite {p!r} does not exist')   # an explicit path that is wrong is an error, not a hint
    w = shutil.which('aseprite')
    if w:
        return w
    tried.append('aseprite on PATH: not found')
    raise Fail('Aseprite not found. Looked in:\n  ' + '\n  '.join(tried) + '\nPass --aseprite PATH or set ASEPRITE_EXE.')


def bundled_palettes(exe):
    """{stem: path} for palette files under <aseprite dir>/data/extensions/*/ (first wins)."""
    root = Path(exe).parent / 'data' / 'extensions'
    found = {}
    if root.is_dir():
        for ext_dir in sorted(root.iterdir()):
            if not ext_dir.is_dir():
                continue
            for f in sorted(ext_dir.iterdir()):
                if f.suffix.lower() in ('.gpl', '.pal', '.hex', '.act') and f.stem.lower() not in found:
                    found[f.stem.lower()] = str(f)
    return found


def resolve_palette(spec, exe):
    if os.path.isfile(spec):
        return str(Path(spec).resolve())
    pals = bundled_palettes(exe)
    hit = pals.get(spec.lower())
    if hit:
        return hit
    raise Fail(f'palette {spec!r} is neither a file nor a bundled palette name. '
               'Run --list-palettes to see the bundled names.')


# ---------------------------------------------------------------- running Aseprite

def run_aseprite(exe, args, user_dir, cwd=None):
    env = dict(os.environ, ASEPRITE_USER_FOLDER=str(user_dir))
    try:
        return subprocess.run([exe, '-b'] + args, env=env, cwd=cwd, capture_output=True,
                              text=True, encoding='utf-8', errors='replace', timeout=TIMEOUT)
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or b'')
        out = out.decode('utf-8', 'replace') if isinstance(out, bytes) else out
        raise Fail(f'Aseprite did not finish within {TIMEOUT}s and was stopped. Output so far:\n{out}')


def show(proc):
    if proc is None:
        return ''
    return f'\n--- Aseprite exit code {proc.returncode} ---\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}'


# ---------------------------------------------------------------- argument parsing

def parse_wh(s, flag, sep='x'):
    m = re.fullmatch(rf'\s*(\d+)\s*[{sep}X]\s*(\d+)\s*', s)
    if not m or int(m.group(1)) < 1 or int(m.group(2)) < 1:
        raise Fail(f'{flag} expects two positive integers like 16{sep}16, got {s!r}')
    return int(m.group(1)), int(m.group(2))


def parse_args(argv):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0], usage=argparse.SUPPRESS)
    ap.add_argument('out_dir', nargs='?')
    ap.add_argument('--name')
    src = ap.add_mutually_exclusive_group()
    src.add_argument('--sheet', help='sprite sheet PNG (equal cells)')
    src.add_argument('--frames', help='folder or glob of equal-size PNG frames')
    cut = ap.add_mutually_exclusive_group()
    cut.add_argument('--cell', help='cell size WxH, e.g. 16x16')
    cut.add_argument('--grid', help='grid COLSxROWS, e.g. 4x3')
    tg = ap.add_mutually_exclusive_group()
    tg.add_argument('--row-tags', help='comma list: one animation name per sheet row')
    tg.add_argument('--tags', help='name:from-to[:direction[:repeats]],... (1-based, over kept frames)')
    ap.add_argument('--fps', type=float, default=10.0)
    ap.add_argument('--tag-fps', help='name=N,name=N overrides')
    ap.add_argument('--key', default='none', help='auto | RRGGBB | none')
    ap.add_argument('--keep-empty', action='store_true')
    pal = ap.add_mutually_exclusive_group()
    pal.add_argument('--palette', help='palette file or bundled name')
    pal.add_argument('--max-colors', type=int, help='quantize to at most N colours')
    ap.add_argument('--dither', choices=DITHERS, default='none')
    ap.add_argument('--alpha-threshold', type=int, default=128)
    ap.add_argument('--pivot', help='bottom-center | center | X,Y')
    ap.add_argument('--sheet-type', choices=['packed', 'rows', 'columns', 'horizontal', 'vertical'], default='packed')
    ap.add_argument('--padding', type=int, default=1)
    ap.add_argument('--extrude', action='store_true')
    ap.add_argument('--trim', action='store_true')
    ap.add_argument('--json-format', choices=['array', 'hash'], default='array')
    ap.add_argument('--aseprite')
    ap.add_argument('--list-palettes', action='store_true')
    ap.add_argument('--keep-temp', action='store_true')
    a = ap.parse_args(argv)
    a._ap = ap
    return a


def validate_args(a):
    """Everything checkable without Aseprite or image data. Raises Fail."""
    if a.list_palettes:
        return
    if not a.out_dir:
        raise Fail('OUT_DIR is required')
    if not a.name:
        raise Fail('--name is required')
    if re.search(r'[\\/:*?"<>|]', a.name):
        raise Fail(f'--name {a.name!r} must be a plain file name (no path separators or reserved characters)')
    if not (a.sheet or a.frames):
        raise Fail('give an input: --sheet PNG (with --cell or --grid) or --frames DIR_OR_GLOB')
    if a.sheet and not (a.cell or a.grid):
        raise Fail('--sheet needs --cell WxH or --grid COLSxROWS')
    if a.frames and (a.cell or a.grid):
        raise Fail('--cell / --grid only apply to --sheet input')
    if a.row_tags and not a.sheet:
        raise Fail('--row-tags only works with --sheet input (use --tags for --frames)')
    if a.cell:
        parse_wh(a.cell, '--cell')
    if a.grid:
        parse_wh(a.grid, '--grid')
    if a.fps <= 0:
        raise Fail('--fps must be positive')
    if not 0 <= a.alpha_threshold <= 255:
        raise Fail('--alpha-threshold must be 0..255')
    if a.max_colors is not None and not 1 <= a.max_colors <= 255:
        raise Fail('--max-colors must be 1..255 (index 0 is reserved for transparency)')
    if a.dither != 'none' and not (a.palette or a.max_colors):
        raise Fail('--dither needs a palette lock: add --palette or --max-colors')
    if a.padding < 0:
        raise Fail('--padding must be >= 0')
    if a.extrude and a.padding < 1:
        raise Fail('--extrude needs --padding >= 1 (the extruded edge lives in the padding)')
    if a.key not in ('auto', 'none') and not re.fullmatch(r'#?[0-9a-fA-F]{6}', a.key):
        raise Fail(f'--key must be auto, none or RRGGBB, got {a.key!r}')
    if a.pivot and a.pivot not in ('bottom-center', 'center') and not re.fullmatch(r'\s*\d+\s*,\s*\d+\s*', a.pivot):
        raise Fail(f'--pivot must be bottom-center, center or X,Y, got {a.pivot!r}')


def parse_tags(spec, nframes):
    """'name:from-to[:direction[:repeats]],...' -> [{name, from, to, dir, repeats}]"""
    tags, seen = [], set()
    for item in [s.strip() for s in spec.split(',') if s.strip()]:
        parts = [p.strip() for p in item.split(':')]
        if len(parts) < 2 or len(parts) > 4 or not parts[0]:
            raise Fail(f'bad tag {item!r}: expected name:from-to[:direction[:repeats]]')
        name = parts[0]
        m = re.fullmatch(r'(\d+)(?:\s*-\s*(\d+))?', parts[1])
        if not m:
            raise Fail(f'bad frame range {parts[1]!r} in tag {name!r}: expected from-to, e.g. 1-6')
        lo = int(m.group(1)); hi = int(m.group(2) or m.group(1))
        direction = parts[2].lower() if len(parts) > 2 and parts[2] else 'forward'
        if direction not in DIRECTIONS:
            raise Fail(f'tag {name!r}: direction {direction!r} must be one of {", ".join(DIRECTIONS)}')
        repeats = None
        if len(parts) > 3 and parts[3]:
            if not parts[3].isdigit() or int(parts[3]) < 1:
                raise Fail(f'tag {name!r}: repeats must be a positive integer, got {parts[3]!r}')
            repeats = int(parts[3])
        if name in seen:
            raise Fail(f'tag name {name!r} is used more than once')
        seen.add(name)
        if lo < 1 or hi > nframes or lo > hi:
            raise Fail(f'tag {name!r}: frames {lo}-{hi} are out of range (there are {nframes} kept frames, numbered 1..{nframes})')
        tags.append({'name': name, 'from': lo, 'to': hi, 'dir': direction, 'repeats': repeats})
    if not tags:
        raise Fail('--tags is empty')
    return tags


def parse_tag_fps(spec, tags):
    out = {}
    names = {t['name'] for t in tags}
    for item in [s.strip() for s in spec.split(',') if s.strip()]:
        n, eq, v = item.partition('=')
        n = n.strip()
        try:
            fps = float(v)
        except ValueError:
            fps = 0
        if not eq or fps <= 0:
            raise Fail(f'bad --tag-fps entry {item!r}: expected name=N with N > 0')
        if n not in names:
            raise Fail(f'--tag-fps names {n!r}, which is not a tag (tags: {", ".join(sorted(names)) or "none"})')
        out[n] = fps
    return out


# ---------------------------------------------------------------- reading frames

def key_out(im, rgb):
    """Pixels whose RGB equals `rgb` exactly become fully transparent (and black underneath)."""
    r, g, b, _ = im.split()
    m = ImageChops.multiply(ImageChops.multiply(r.point(lambda v: 255 if v == rgb[0] else 0),
                                                g.point(lambda v: 255 if v == rgb[1] else 0)),
                            b.point(lambda v: 255 if v == rgb[2] else 0))
    return Image.composite(Image.new('RGBA', im.size, (0, 0, 0, 0)), im, m)


def resolve_key(spec, first_im, notes):
    if spec == 'none':
        return None
    if spec == 'auto':
        px = first_im.getpixel((0, 0))
        if px[3] == 0:
            notes.append('--key auto: top-left pixel is already transparent, nothing keyed')
            return None
        return px[:3]
    h = spec.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def is_empty(im):
    return im.getchannel('A').getbbox() is None


def load_frames(a, notes):
    """-> (cells [RGBA images], row_of [sheet row per kept frame or None], rows, dropped, total)"""
    if a.sheet:
        if not os.path.isfile(a.sheet):
            raise Fail(f'sheet not found: {a.sheet}')
        sheet = Image.open(a.sheet).convert('RGBA')
        key = resolve_key(a.key, sheet, notes)
        if key is not None:
            sheet = key_out(sheet, key)
        W, H = sheet.size
        if a.cell:
            cw, ch = parse_wh(a.cell, '--cell')
            if W % cw or H % ch:
                raise Fail(f'sheet is {W}x{H}, which is not a whole number of {cw}x{ch} cells. '
                           'Run cut_cells.py first to make equal cells (nothing is padded or cropped silently).')
            cols, rows = W // cw, H // ch
        else:
            cols, rows = parse_wh(a.grid, '--grid')
            if W % cols or H % rows:
                raise Fail(f'sheet is {W}x{H}, which does not divide into a {cols}x{rows} grid. '
                           'Run cut_cells.py first to make equal cells.')
            cw, ch = W // cols, H // rows
        cells, row_of, dropped = [], [], 0
        for r in range(rows):
            for c in range(cols):
                cell = sheet.crop((c * cw, r * ch, (c + 1) * cw, (r + 1) * ch))
                if is_empty(cell) and not a.keep_empty:
                    dropped += 1
                    continue
                cells.append(cell)
                row_of.append(r)
        return cells, row_of, rows, dropped, rows * cols
    # --frames
    if os.path.isdir(a.frames):
        paths = [str(p) for p in Path(a.frames).iterdir() if p.is_file() and p.suffix.lower() == '.png']
    else:
        paths = [p for p in glob.glob(a.frames) if os.path.isfile(p)]
    if not paths:
        raise Fail(f'no PNG frames found for --frames {a.frames!r}')
    paths.sort(key=lambda p: natural_key(os.path.basename(p)))
    ims = [Image.open(p).convert('RGBA') for p in paths]
    sizes = {im.size for im in ims}
    if len(sizes) > 1:
        detail = ', '.join(f'{os.path.basename(p)}={im.size[0]}x{im.size[1]}' for p, im in zip(paths, ims))
        raise Fail(f'frames are not all the same size ({detail}). Run cut_cells.py first to cut equal cells; '
                   'ase_pack never pads or resizes silently.')
    key = resolve_key(a.key, ims[0], notes)
    if key is not None:
        ims = [key_out(im, key) for im in ims]
    return ims, None, None, 0, len(ims)


# ---------------------------------------------------------------- palette from art (--max-colors)

def quantize_palette(cells, n, thr):
    """At most n colours from the opaque pixels of all cells. Exact when the art has <= n colours."""
    counts = {}
    for im in cells:
        for cnt, px in im.getcolors(maxcolors=im.width * im.height + 1) or []:
            if px[3] >= thr:
                counts[px[:3]] = counts.get(px[:3], 0) + cnt
    if not counts:
        raise Fail('--max-colors: the art has no opaque pixels')
    if len(counts) <= n:
        return [list(c) for c in sorted(counts)]
    flat = []
    for c, cnt in counts.items():
        flat.extend([c] * cnt)
    strip = Image.new('RGB', (len(flat), 1))
    strip.putdata(flat)
    q = strip.quantize(colors=n, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    pal = q.getpalette()
    used = sorted({idx for _, idx in q.getcolors(maxcolors=256)})
    return [[pal[i * 3], pal[i * 3 + 1], pal[i * 3 + 2]] for i in used]


# ---------------------------------------------------------------- verification

def read_aseprite_header(path):
    with open(path, 'rb') as f:
        h = f.read(16)
    if len(h) < 14:
        return None, None
    return int.from_bytes(h[4:6], 'little'), int.from_bytes(h[12:14], 'little')


def verify(a, stats, outs, expected_tags):
    """Raises Fail on the first problem; returns (json_data, colours_used)."""
    for label, p in outs.items():
        if not os.path.isfile(p) or os.path.getsize(p) == 0:
            raise Fail(f'output {label} is missing or empty: {p}')
    magic, depth = read_aseprite_header(outs['aseprite'])
    if magic != 0xA5E0:
        raise Fail('the .aseprite file has a bad header (magic is not 0xA5E0)')
    want_depth = 8 if stats.get('locked') else 32
    if depth != want_depth:
        raise Fail(f'the .aseprite colour depth is {depth}, expected {want_depth}')
    try:
        data = json.loads(Path(outs['json']).read_text(encoding='utf-8'))
    except ValueError as e:
        raise Fail(f'the JSON data file does not parse: {e}')
    fr = data.get('frames')
    nfr = len(fr) if fr is not None else -1
    if nfr != stats['frames']:
        raise Fail(f'JSON frame count {nfr} does not equal the kept-frame count {stats["frames"]}')
    ft = {t['name']: t for t in data.get('meta', {}).get('frameTags', [])}
    for t in expected_tags:
        got = ft.get(t['name'])
        if got is None:
            raise Fail(f'tag {t["name"]!r} is missing from meta.frameTags')
        if got['from'] != t['from'] - 1 or got['to'] != t['to'] - 1 or got['direction'] != t['dir']:
            raise Fail(f'tag {t["name"]!r} came out as {got["from"]}-{got["to"]} {got["direction"]}, '
                       f'expected {t["from"] - 1}-{t["to"] - 1} {t["dir"]}')
        if t['repeats'] is not None and str(got.get('repeat')) != str(t['repeats']):
            raise Fail(f'tag {t["name"]!r} repeat is {got.get("repeat")!r}, expected {t["repeats"]}')
    if a.pivot:
        sl = [s for s in data.get('meta', {}).get('slices', []) if s.get('name') == 'anchor']
        if not sl:
            raise Fail('slice "anchor" is missing from meta.slices')
    try:
        sheet = Image.open(outs['png'])
        sheet.load()
    except Exception as e:
        raise Fail(f'the sheet PNG does not open in Pillow: {e}')
    if sheet.mode != 'RGBA':
        raise Fail(f'the sheet PNG is {sheet.mode}, expected RGBA')
    colours = set()
    opaque = 0
    for cnt, px in sheet.getcolors(maxcolors=sheet.width * sheet.height + 1) or []:
        if px[3] > 0:
            colours.add(px[:3])
            opaque += cnt
    if stats.get('locked'):
        pal = {tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) for h in stats['palette']}
        stray = sorted(c for c in colours if c not in pal)
        if stray:
            raise Fail(f'{len(stray)} sheet colour(s) are not in the locked palette, e.g. #%02x%02x%02x' % stray[0])
        if stats['opaque_before'] != stats['opaque_after']:
            raise Fail(f'palette lock changed the opaque-pixel count: {stats["opaque_before"]} before, '
                       f'{stats["opaque_after"]} after')
        # Aseprite packs identical frames into ONE rectangle, so count opaque pixels per frame
        # (each frame's own rectangle, duplicates counted once per frame), not over the whole sheet
        alpha, memo, per_frame = sheet.getchannel('A'), {}, 0
        for f in (fr.values() if isinstance(fr, dict) else fr):
            r = f['frame']
            box = (r['x'], r['y'], r['x'] + r['w'], r['y'] + r['h'])
            if box not in memo:
                memo[box] = sum(alpha.crop(box).histogram()[1:])
            per_frame += memo[box]
        if per_frame != stats['opaque_after']:
            raise Fail(f'the exported sheet holds {per_frame} opaque pixels across its frames, '
                       f'the locked sprite has {stats["opaque_after"]}')
    return data, colours


# ---------------------------------------------------------------- main

def pack(a):
    if a.list_palettes:
        exe = find_aseprite(a.aseprite)
        pals = bundled_palettes(exe)
        for stem in sorted(pals):
            print(f'{stem}\t{Path(pals[stem]).parent.name}')
        print(f'{len(pals)} bundled palettes under {Path(exe).parent / "data" / "extensions"}', file=sys.stderr)
        return 0

    notes = []
    cells, row_of, nrows, dropped, total = load_frames(a, notes)
    n = len(cells)
    if n == 0:
        raise Fail('no frames left: every cell was empty (try --keep-empty or check --key)')
    cw, ch = cells[0].size

    # tags (all validation happens before Aseprite starts)
    tags = []
    if a.row_tags:
        names = [s.strip() for s in a.row_tags.split(',')]
        if any(not s for s in names) or len(set(names)) != len(names):
            raise Fail('--row-tags names must be non-empty and unique')
        if len(names) != nrows:
            raise Fail(f'--row-tags has {len(names)} names but the sheet has {nrows} rows')
        for r, name in enumerate(names):
            idx = [i + 1 for i, rr in enumerate(row_of) if rr == r]
            if not idx:
                raise Fail(f'row {r + 1} ({name!r}) has no kept frames (all cells empty); fix the sheet or the --row-tags list')
            tags.append({'name': name, 'from': idx[0], 'to': idx[-1], 'dir': 'forward', 'repeats': None})
    elif a.tags:
        tags = parse_tags(a.tags, n)
    tag_fps = parse_tag_fps(a.tag_fps, tags) if a.tag_fps else {}
    if a.tag_fps and not tags:
        raise Fail('--tag-fps needs tags (--row-tags or --tags)')
    base_ms = max(1, round(1000 / a.fps))
    durations = [base_ms] * n
    for t in tags:
        if t['name'] in tag_fps:
            for i in range(t['from'] - 1, t['to']):
                durations[i] = max(1, round(1000 / tag_fps[t['name']]))
    pivot = None
    if a.pivot == 'bottom-center':
        pivot = (cw // 2, ch - 1)
    elif a.pivot == 'center':
        pivot = (cw // 2, ch // 2)
    elif a.pivot:
        x, y = (int(v) for v in a.pivot.split(','))
        if x >= cw or y >= ch:
            raise Fail(f'--pivot {x},{y} is outside the {cw}x{ch} cell')
        pivot = (x, y)
    exe = find_aseprite(a.aseprite)          # only now: every input/tag error above is reported before Aseprite is needed
    palette_file = resolve_palette(a.palette, exe) if a.palette else None
    if a.trim:
        notes.append('--trim trims each frame: the engine must apply spriteSourceSize (frame offsets) from the JSON')

    out_dir = Path(a.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix='ase_pack_'))
    try:
        (work / 'user').mkdir()
        (work / 'cells').mkdir()
        (work / 'out').mkdir()
        paths = []
        for i, im in enumerate(cells):
            p = work / 'cells' / f'f{i + 1:05d}.png'
            im.save(p)
            paths.append(fwd(p))
        job = {'frames': paths, 'durations': durations, 'alpha_threshold': a.alpha_threshold, 'dither': a.dither,
               'tags': tags, 'stats': fwd(work / 'stats.json'), 'out_aseprite': fwd(work / 'out' / f'{a.name}.aseprite')}
        if pivot:
            job['pivot'] = {'x': pivot[0], 'y': pivot[1]}
        if palette_file:
            job['palette'] = {'file': fwd(palette_file)}
        elif a.max_colors:
            job['palette'] = {'colors': quantize_palette(cells, a.max_colors, a.alpha_threshold)}
        (work / 'job.json').write_text(json.dumps(job), encoding='utf-8')

        # 1. build
        proc = run_aseprite(exe, ['--script-param', f'job={fwd(work / "job.json")}', '--script', str(LUA)], work / 'user')
        stats_path = work / 'stats.json'
        if not stats_path.is_file():
            raise Fail('Aseprite did not write the stats file, so the build script failed or never ran.' + show(proc), proc)
        stats = json.loads(stats_path.read_text(encoding='utf-8'))
        if not stats.get('ok'):
            raise Fail(f'build script reported an error: {stats.get("error", "unknown")}' + show(proc), proc)

        # 2. export (cwd = work/out and relative names keep meta.image = "<name>.png")
        name = a.name
        args = [f'{name}.aseprite', '--color-mode', 'rgb', '--sheet', f'{name}.png', '--data', f'{name}.json',
                '--format', f'json-{a.json_format}', '--sheet-type', a.sheet_type,
                '--shape-padding', str(a.padding), '--border-padding', str(a.padding)]
        if a.extrude:
            args.append('--extrude')
        if a.trim:
            args.append('--trim')
        args += ['--list-tags', '--list-slices', '--list-layers']
        proc = run_aseprite(exe, args, work / 'user', cwd=str(work / 'out'))
        outs = {'aseprite': work / 'out' / f'{name}.aseprite', 'png': work / 'out' / f'{name}.png',
                'json': work / 'out' / f'{name}.json'}
        outs = {k: str(v) for k, v in outs.items()}
        try:
            data, colours = verify(a, stats, outs, tags)
        except Fail as e:
            raise Fail(f'verification failed: {e}' + show(proc), proc)

        final = {}
        for k, p in outs.items():
            final[k] = str(out_dir / os.path.basename(p))
            shutil.copy2(p, final[k])
    finally:
        if a.keep_temp:
            print(f'temp kept: {work}')
        else:
            shutil.rmtree(work, ignore_errors=True)

    for note in notes:
        print(f'WARNING: {note}')
    tag_txt = ', '.join(f'{t["name"]} {t["from"] - 1}-{t["to"] - 1}' + (f' {t["dir"]}' if t['dir'] != 'forward' else '')
                        for t in tags) or 'none'
    lock = ''
    if stats.get('locked'):
        lock = f', palette locked ({len(stats["palette"])} entries, {stats["opaque_after"]} opaque px unchanged)'
    print(f'{n} frames kept, {dropped} dropped ({total} cells), cell {cw}x{ch}, tags: {tag_txt}, '
          f'{len(colours)} colours used{lock}')
    print(f'  {final["aseprite"]}\n  {final["png"]}\n  {final["json"]}')
    return 0


def main(argv=None):
    a = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        validate_args(a)
        return pack(a)
    except Fail as e:
        print(f'ase_pack: error: {e}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
