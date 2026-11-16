"""Self-test for ase_pack.py: builds synthetic fixtures with Pillow in a temp folder, runs
tests T1-T8 (plus a T9 regression) and the v1.1 --defringe tests T10-T12 against the real Aseprite
(headless), and exits 0 only if every test passes.

  C:\\AI-Shared\\python.exe ase_pack_selftest.py

After the tests it also asserts that no Aseprite.exe started during the run is still alive
and that the real config folder %APPDATA%\\Aseprite\\files has the same file count as before.
"""
import colorsys, json, os, re, shutil, subprocess, sys, tempfile, traceback
from pathlib import Path
from PIL import Image, ImageChops, ImageDraw, ImageFilter

HERE = Path(__file__).resolve().parent
TOOL = HERE / 'ase_pack.py'
MAGENTA = (255, 0, 255)
WHITE = (249, 248, 248)                                      # #f9f8f8, the fringe colour
GLINT = (4, 6)                                               # enclosed white pixel, inside the rectangle of make_cell
NES_GPL = Path(r'C:\Program Files (x86)\Steam\steamapps\common\Aseprite\data\extensions\hardware-palettes\nes.gpl')


# ---------------------------------------------------------------- helpers

def aseprite_pids():
    out = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq Aseprite.exe', '/FO', 'CSV', '/NH'],
                         capture_output=True, text=True).stdout
    return {int(m.group(1)) for m in re.finditer(r'"Aseprite\.exe","(\d+)"', out)}


def config_file_count():
    d = Path(os.environ.get('APPDATA', '')) / 'Aseprite' / 'files'
    return sum(1 for _ in d.rglob('*')) if d.is_dir() else 0


def hue(i, n, s=0.8, v=0.9):
    return tuple(int(c * 255) for c in colorsys.hsv_to_rgb(i / n, s, v))


def make_cell(i, size, key=None):
    """A distinct simple shape in several colours; `key` fills the background (None = transparent)."""
    w, h = size
    im = Image.new('RGBA', size, (key + (255,)) if key else (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle([2, 3, 8 + i % 4, h - 5], fill=hue(i, 12) + (255,))
    d.ellipse([w // 2 - 2, 1, w - 3, h // 2 + 1], fill=hue(i + 6, 12, 0.7, 0.7) + (255,))
    d.line([(1, h - 2), (w - 2, h - 2 - i % 3)], fill=hue(i + 3, 12, 1.0, 1.0) + (255,))
    d.point((0, 1), fill=(20 + i, 20, 20, 255))            # a near-black pixel, never the key (and not the top-left corner)
    return im


def make_sheet(path):
    """4x3 grid of 16x16 cells on magenta; the last two cells are background only."""
    sheet = Image.new('RGBA', (64, 48), MAGENTA + (255,))
    for i in range(10):
        sheet.paste(make_cell(i, (16, 16), MAGENTA), ((i % 4) * 16, (i // 4) * 16))
    sheet.save(path)
    # the cells as they must come out (magenta keyed to transparent), in kept order
    return [expected_keyed(sheet.crop(((i % 4) * 16, (i // 4) * 16, (i % 4) * 16 + 16, (i // 4) * 16 + 16)))
            for i in range(10)]


def make_ring_sheet(path):
    """The T1 sheet where every non-empty cell's shape also has a 1-pixel white ring around its outside
    plus one white pixel enclosed inside the shape. Returns (the cells as they must come out of --defringe,
    i.e. the same fixture drawn without the ring, and the number of ring pixels drawn in all)."""
    sheet = Image.new('RGBA', (64, 48), MAGENTA + (255,))
    expected, ring_total = [], 0
    for i in range(10):
        base = make_cell(i, (16, 16))
        base.putpixel(GLINT, WHITE + (255,))
        mask = base.getchannel('A')
        ring = ImageChops.subtract(mask.filter(ImageFilter.MaxFilter(3)), mask)   # 8-neighbour dilation minus the shape
        ring.putpixel((0, 0), 0)                  # keep the sheet's top-left pixel magenta, so --key auto still finds the key
        ring_total += sum(1 for v in ring.getdata() if v)
        ringed = base.copy()
        ringed.paste(Image.new('RGBA', base.size, WHITE + (255,)), (0, 0), ring)
        cell = Image.new('RGBA', base.size, MAGENTA + (255,))
        cell.alpha_composite(ringed)
        sheet.paste(cell, ((i % 4) * 16, (i // 4) * 16))
        expected.append(expected_keyed(base))     # make_cell's line is exactly magenta for i=7, so --key removes it, as in T1
    sheet.save(path)
    return expected, ring_total


def light_opaque(im, n=180):
    """Opaque pixels with min(R,G,B) > n."""
    return sum(1 for p in im.convert('RGBA').getdata() if p[3] > 0 and min(p[:3]) > n)


def expected_keyed(im):
    px = im.load()
    out = im.copy()
    po = out.load()
    for y in range(im.height):
        for x in range(im.width):
            if px[x, y][:3] == MAGENTA:
                po[x, y] = (0, 0, 0, 0)
    return out


def run(args, env=None):
    p = subprocess.run([sys.executable, str(TOOL)] + [str(a) for a in args], capture_output=True, text=True,
                       encoding='utf-8', errors='replace', timeout=240, env=env)
    return p.returncode, p.stdout, p.stderr


def must_run_ok(args):
    rc, out, err = run(args)
    assert rc == 0, f'exit {rc}\nstdout:\n{out}\nstderr:\n{err}'
    return out


def load_out(out_dir, name):
    j = json.loads((Path(out_dir) / f'{name}.json').read_text(encoding='utf-8'))
    png = Image.open(Path(out_dir) / f'{name}.png')
    png.load()
    return j, png


def frame_list(j):
    f = j['frames']
    return list(f.values()) if isinstance(f, dict) else f


def opaque_pixels(png):
    return sum(1 for p in png.getdata() if p[3] > 0)


def opaque_colours(png):
    return {p[:3] for p in png.getdata() if p[3] > 0}


def aseprite_depth(path):
    h = Path(path).read_bytes()[:16]
    assert int.from_bytes(h[4:6], 'little') == 0xA5E0, 'bad .aseprite magic'
    return int.from_bytes(h[12:14], 'little')


def tag_map(j):
    return {t['name']: t for t in j['meta']['frameTags']}


def cell_of(j, png, i):
    r = frame_list(j)[i]['frame']
    return png.crop((r['x'], r['y'], r['x'] + r['w'], r['y'] + r['h']))


def same_art(a, b):
    """Same alpha everywhere and same RGB wherever opaque."""
    if a.size != b.size:
        return False
    pa, pb = a.convert('RGBA').load(), b.convert('RGBA').load()
    for y in range(a.height):
        for x in range(a.width):
            u, v = pa[x, y], pb[x, y]
            if (u[3] > 0) != (v[3] > 0) or (u[3] > 0 and u[:3] != v[:3]):
                return False
    return True


def parse_gpl(path):
    cols = set()
    for line in Path(path).read_text(encoding='utf-8', errors='replace').splitlines():
        m = re.match(r'\s*(\d+)\s+(\d+)\s+(\d+)', line)
        if m:
            cols.add(tuple(int(g) for g in m.groups()))
    return cols


# ---------------------------------------------------------------- tests

class Ctx:
    pass


def t1(c):
    out = c.tmp / 't1'
    o = must_run_ok([out, '--name', 'hero', '--sheet', c.sheet, '--cell', '16x16', '--key', 'auto',
                     '--row-tags', 'idle,walk,attack', '--fps', 8])
    j, png = load_out(out, 'hero')
    fr = frame_list(j)
    assert len(fr) == 10, f'{len(fr)} frames'
    tm = tag_map(j)
    for name, a, b in (('idle', 0, 3), ('walk', 4, 7), ('attack', 8, 9)):
        assert (tm[name]['from'], tm[name]['to']) == (a, b), f'tag {name}: {tm[name]}'
    assert all(f['duration'] == 125 for f in fr), [f['duration'] for f in fr]
    assert png.mode == 'RGBA', png.mode
    assert MAGENTA not in opaque_colours(png), 'opaque magenta pixel in the sheet'
    assert j['meta']['image'] == 'hero.png', j['meta']['image']
    assert aseprite_depth(out / 'hero.aseprite') == 32
    for i in range(10):
        assert same_art(cell_of(j, png, i), c.expected[i]), f'frame {i} does not match the fixture cell'
    c.t1_opaque = opaque_pixels(png)
    assert c.t1_opaque > 0
    return f'10 frames, tags idle 0-3 / walk 4-7 / attack 8-9, all durations 125, RGBA, {c.t1_opaque} opaque px, frames match fixture'


def t2(c):
    out = c.tmp / 't2'
    must_run_ok([out, '--name', 'hero', '--sheet', c.sheet, '--cell', '16x16', '--key', 'auto',
                 '--row-tags', 'idle,walk,attack', '--fps', 8, '--palette', 'nes'])
    j, png = load_out(out, 'hero')
    nes = parse_gpl(NES_GPL)
    assert len(nes) > 10, 'could not read the NES palette'
    cols = opaque_colours(png)
    stray = cols - nes
    assert not stray, f'colours outside the NES palette: {sorted(stray)[:3]}'
    n = opaque_pixels(png)
    assert n == c.t1_opaque, f'opaque px {n} != T1 {c.t1_opaque}'
    assert aseprite_depth(out / 'hero.aseprite') == 8, 'saved .aseprite is not indexed'
    assert png.mode == 'RGBA'
    assert len(frame_list(j)) == 10
    # transparency survived frame by frame: same opaque mask as the fixture
    for i in range(10):
        a = cell_of(j, png, i).getchannel('A').point(lambda v: 255 if v else 0)
        b = c.expected[i].getchannel('A').point(lambda v: 255 if v else 0)
        assert a.tobytes() == b.tobytes(), f'frame {i}: opaque mask changed by the palette lock'
    return f'{len(cols)} colours, all in NES; opaque px {n} == T1; .aseprite depth 8; PNG RGBA; per-frame masks identical'


def t3(c):
    out = c.tmp / 't3'
    must_run_ok([out, '--name', 'hero', '--sheet', c.sheet, '--cell', '16x16', '--key', 'auto',
                 '--row-tags', 'idle,walk,attack', '--fps', 8, '--max-colors', 4])
    j, png = load_out(out, 'hero')
    cols = opaque_colours(png)
    assert 1 <= len(cols) <= 4, f'{len(cols)} opaque colours'
    n = opaque_pixels(png)
    assert n == c.t1_opaque, f'opaque px {n} != T1 {c.t1_opaque}'
    assert aseprite_depth(out / 'hero.aseprite') == 8
    return f'{len(cols)} opaque colours (limit 4), opaque px {n} == T1'


def t4(c):
    d = c.tmp / 't4_frames'
    d.mkdir()
    order = ['f_1', 'f_2', 'f_3', 'f_4', 'f_5', 'f_10']      # f_10 sorts second as text, last as numbers
    src = []
    for k, stem in enumerate(order):
        im = make_cell(k, (24, 24), (30, 30, 60))
        im.save(d / f'{stem}.png')
        src.append(im)
    out = c.tmp / 't4'
    must_run_ok([out, '--name', 'run', '--frames', d, '--tags', 'run:1-6:pingpong:2', '--tag-fps', 'run=12'])
    j, png = load_out(out, 'run')
    fr = frame_list(j)
    assert len(fr) == 6
    t = tag_map(j)['run']
    assert (t['from'], t['to'], t['direction']) == (0, 5, 'pingpong'), t
    assert str(t.get('repeat')) == '2', t
    assert all(f['duration'] == 83 for f in fr), [f['duration'] for f in fr]
    for i in range(6):
        assert same_art(cell_of(j, png, i), src[i]), f'frame {i} is not {order[i]} (natural sort order broken)'
    return 'tag run 0-5 pingpong repeat "2", durations 83, frame order f_1..f_5,f_10 (natural sort)'


def t5(c):
    d = c.tmp / 't5_frames'
    d.mkdir()
    for i in range(5):
        make_cell(i, (24, 24), (30, 30, 60)).save(d / f'f_{i + 1}.png')
    make_cell(5, (32, 24), (30, 30, 60)).save(d / 'f_6.png')
    rc, out, err = run([c.tmp / 't5', '--name', 'bad', '--frames', d])
    assert rc != 0, 'mixed sizes should fail'
    assert 'cut_cells.py' in out + err, f'message does not mention cut_cells.py:\n{err}'
    assert not (c.tmp / 't5' / 'bad.png').exists()
    return f'exit {rc}, message mentions cut_cells.py'


def t6(c):
    d = c.tmp / 't6_frames'
    d.mkdir()
    for i in range(6):
        make_cell(i, (24, 24), (30, 30, 60)).save(d / f'f_{i + 1}.png')
    marker = c.tmp / 'stub_ran.txt'
    stub = c.tmp / 'stub_aseprite.cmd'
    stub.write_text(f'@echo started> "{marker}"\r\n', encoding='ascii')
    env = dict(os.environ, ASEPRITE_EXE=str(stub))
    rc, out, err = run([c.tmp / 't6', '--name', 'x', '--frames', d, '--tags', 'x:1-99'], env=env)
    assert rc != 0, 'out-of-range tag should fail'
    assert 'out of range' in err, f'unexpected message: {err}'
    assert not marker.exists(), 'Aseprite (the stub) was started before the tag error'
    return f'exit {rc}, "{err.strip().splitlines()[0][:90]}", Aseprite stub never started'


def t7(c):
    out = c.tmp / 't7'
    must_run_ok([out, '--name', 'hero', '--sheet', c.sheet, '--cell', '16x16', '--key', 'auto',
                 '--row-tags', 'idle,walk,attack', '--fps', 8, '--pivot', 'bottom-center'])
    j, _ = load_out(out, 'hero')
    sl = [s for s in j['meta']['slices'] if s['name'] == 'anchor']
    assert sl, f'no anchor slice: {j["meta"]["slices"]}'
    k = sl[0]['keys'][0]
    assert (k['pivot']['x'], k['pivot']['y']) == (8, 15), k
    assert (k['bounds']['w'], k['bounds']['h']) == (16, 16), k
    return f'anchor slice pivot ({k["pivot"]["x"]},{k["pivot"]["y"]}), bounds {k["bounds"]["w"]}x{k["bounds"]["h"]}'


def t8(c):
    out = c.tmp / 't8'
    must_run_ok([out, '--name', 'hero', '--sheet', c.sheet, '--grid', '4x3', '--key', 'auto',
                 '--row-tags', 'idle,walk,attack', '--fps', 8])
    j8, p8 = load_out(out, 'hero')
    j1, p1 = load_out(c.tmp / 't1', 'hero')
    assert p8.size == p1.size and p8.tobytes() == p1.tobytes(), 'sheet PNG differs from T1'
    assert frame_list(j8) == frame_list(j1), 'frames differ from T1'
    assert j8['meta']['frameTags'] == j1['meta']['frameTags'], 'tags differ from T1'
    return 'sheet PNG, frames and tags identical to T1'


def t9(c):
    """Regression (extra, not in the spec): identical frames share one rectangle in a packed sheet,
    so the opaque-pixel check must count per frame, not over the whole sheet."""
    d = c.tmp / 't9_frames'
    d.mkdir()
    for i, k in enumerate([0, 0, 1, 1, 2]):
        make_cell(k, (16, 16)).save(d / f'f_{i + 1}.png')
    out = c.tmp / 't9'
    must_run_ok([out, '--name', 'dup', '--frames', d, '--palette', 'nes'])
    j, png = load_out(out, 'dup')
    rects = {tuple(f['frame'].values()) for f in frame_list(j)}
    assert len(frame_list(j)) == 5 and len(rects) < 5, 'expected 5 frames sharing fewer sheet rectangles'
    return f'5 frames, {len(rects)} unique sheet rectangles, palette-lock check passes'


RING_ARGS = ['--key', 'auto', '--row-tags', 'idle,walk,attack', '--fps', 8]


def t10(c):
    out = c.tmp / 't10'
    o = must_run_ok([out, '--name', 'hero', '--sheet', c.ring_sheet, '--cell', '16x16'] + RING_ARGS + ['--defringe'])
    j, png = load_out(out, 'hero')
    assert len(frame_list(j)) == 10, f'{len(frame_list(j))} frames'
    for i in range(10):
        cell = cell_of(j, png, i)
        n_light = light_opaque(cell)
        assert n_light == 1, f'frame {i}: {n_light} light opaque pixels left, expected exactly the enclosed one'
        assert cell.convert('RGBA').getpixel(GLINT)[:3] == WHITE and cell.convert('RGBA').getpixel(GLINT)[3] > 0, \
            f'frame {i}: the enclosed white pixel at {GLINT} was not kept'
        n, want = opaque_pixels(cell), opaque_pixels(c.ring_expected[i])
        assert n == want, f'frame {i}: {n} opaque px, the ring-free fixture has {want}'
        assert same_art(cell, c.ring_expected[i]), f'frame {i} differs from the ring-free fixture'
    m = re.search(r'defringe: (\d+) px removed \(threshold 180\)', o)
    assert m, f'no defringe summary line in the output:\n{o}'
    removed = int(m.group(1))
    assert removed > 0, 'defringe reported 0 px removed'
    assert removed == c.ring_total, f'reported {removed} px removed, the fixture drew {c.ring_total} ring pixels'
    return f'10 frames, exactly 1 light px left per frame (the enclosed one), opaque px per frame match the ring-free fixture, "defringe: {removed} px removed (threshold 180)"'


def t11(c):
    out = c.tmp / 't11'
    o = must_run_ok([out, '--name', 'hero', '--sheet', c.ring_sheet, '--cell', '16x16'] + RING_ARGS)
    j, png = load_out(out, 'hero')
    assert len(frame_list(j)) == 10
    counts = [light_opaque(cell_of(j, png, i)) for i in range(10)]
    assert all(n > 10 for n in counts), f'ring should still be there, light opaque px per frame: {counts}'
    assert 'defringe' not in o, 'defringe summary printed although --defringe was not given'
    return f'ring kept without --defringe: light opaque px per frame {min(counts)}..{max(counts)}'


def t12(c):
    marker = c.tmp / 'stub_ran_t12.txt'
    stub = c.tmp / 'stub_aseprite_t12.cmd'
    stub.write_text(f'@echo started> "{marker}"\r\n', encoding='ascii')
    env = dict(os.environ, ASEPRITE_EXE=str(stub))
    rc, out, err = run([c.tmp / 't12', '--name', 'x', '--sheet', c.ring_sheet, '--cell', '16x16', '--defringe', 300], env=env)
    assert rc != 0, '--defringe 300 should fail'
    assert '--defringe' in err, f'unexpected message: {err}'
    assert not marker.exists(), 'Aseprite (the stub) was started before the --defringe error'
    return f'exit {rc}, "{err.strip().splitlines()[0][:90]}", Aseprite stub never started'


TESTS = [('T1', t1), ('T2', t2), ('T3', t3), ('T4', t4), ('T5', t5), ('T6', t6), ('T7', t7), ('T8', t8), ('T9', t9),
         ('T10', t10), ('T11', t11), ('T12', t12)]


def main():
    c = Ctx()
    c.tmp = Path(tempfile.mkdtemp(prefix='ase_pack_selftest_'))
    before_pids = aseprite_pids()
    before_files = config_file_count()
    results = []
    try:
        c.sheet = c.tmp / 'sheet.png'
        c.expected = make_sheet(c.sheet)
        c.ring_sheet = c.tmp / 'ring_sheet.png'
        c.ring_expected, c.ring_total = make_ring_sheet(c.ring_sheet)
        c.t1_opaque = None
        for name, fn in TESTS:
            try:
                msg = fn(c)
                results.append((name, True, msg))
                print(f'{name} PASS  {msg}')
            except Exception as e:
                results.append((name, False, str(e)))
                print(f'{name} FAIL  {e}')
                if not isinstance(e, AssertionError):
                    traceback.print_exc()
        # whole-run checks
        leftover = aseprite_pids() - before_pids
        ok = not leftover
        results.append(('procs', ok, f'leftover Aseprite.exe PIDs: {sorted(leftover)}'))
        print(f'procs {"PASS" if ok else "FAIL"}  no Aseprite.exe started by the tests is still running' if ok
              else f'procs FAIL  leftover Aseprite.exe PIDs: {sorted(leftover)}')
        after_files = config_file_count()
        ok = after_files == before_files
        results.append(('config', ok, f'{before_files} -> {after_files}'))
        print(f'config {"PASS" if ok else "FAIL"}  %APPDATA%\\Aseprite\\files count {before_files} -> {after_files}')
    finally:
        shutil.rmtree(c.tmp, ignore_errors=True)
    failed = [n for n, ok, _ in results if not ok]
    if failed:
        print(f'FAILED: {", ".join(failed)}')
        return 1
    print(f'ALL PASSED ({len(TESTS)} tests + process and config checks)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
