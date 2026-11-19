"""Offline self-test for sprite_make.py. Needs no ComfyUI: every case but S5/S6 runs
`sprite_make.py --from-image` on a synthetic image drawn here.

  S1  fake pixel art (blocky figure, 8x upscale, slight blur, flat magenta) -> pass; grid <= 64 px,
      <= 24 colours, transparent background, three packed files + report exist, verdict pass
  S2  S1 + a 2 px near-white ring around the figure -> pass; defringe applied, removed > 0
  S3  mostly near-white figure on transparency whose white touches the edge -> defringe skipped
      with the reason recorded, the white pixels still there
  S4  two separate figures of equal size -> exit 1, the one-subject check is the one that failed
  S5  --brief with an unreachable --server -> exit 3, the "not running" message, within 10 s
  S6  bad arguments (--colors 99; --brief with --from-image) -> exit 2
  X1  sprite_make's defringe_frame agrees with ase_pack.py's, pixel for pixel (extra)
  X3  the generation path against a MOCK ComfyUI served from this process on a random local port: prompt and
      graph built right, image fetched and run through the pipeline, time cap -> POST /interrupt -> failed
      attempt, qwen gets one attempt (extra; the real ComfyUI is never touched)
  X4  a source whose background cannot be removed fails honestly when ComfyUI is unreachable (extra)
  X2  nothing under C:\\Claude\\sarges-skills changed except the two new scripts; no new Aseprite
      process is left running (extra, asserted at the end)

Run with the base interpreter:  C:\\AI-Shared\\python.exe sprite_make_selftest.py [--only S1,S2]
Test output goes to Local_Sprite_Lab\\benchmark\\local\\selftest\\run_<timestamp>\\ (kept for looking at);
synthetic inputs live in a tempfile folder that is removed at the end. Exit 0 only if every case passed.
"""
import sys
sys.dont_write_bytecode = True

import argparse
import importlib.util
import io
import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from PIL import Image, ImageChops, ImageDraw, ImageFilter

HERE = Path(__file__).resolve().parent
SPRITE_MAKE = HERE / "sprite_make.py"
SKILLS_ROOT = HERE.parent.parent
ASE_PACK = SKILLS_ROOT / "game-asset-pipeline" / "scripts" / "lane-2d" / "ase_pack.py"
BASE_PY = r"C:\AI-Shared\python.exe"
OUT_ROOT = Path(os.environ.get("SPRITE_MAKE_SELFTEST_OUT") or Path(tempfile.gettempdir()) / "sprite_make_selftest")
OWN_FILES = {SPRITE_MAKE.resolve(), Path(__file__).resolve()}
MAG = (255, 0, 255)
NEAR_WHITE = 180        # min(R,G,B) above this counts as "light", same as defringe
TIMEOUT = 600
ENV = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8"}


# ---------------------------------------------------------------- synthetic art

def figure(art=64):
    """A blocky 38x57 art-pixel adventurer on flat magenta; 1 px details so it is real 1x pixel art."""
    im = Image.new("RGBA", (art, art), MAG + (255,))
    d = ImageDraw.Draw(im)
    r = lambda x0, y0, x1, y1, c: d.rectangle([x0, y0, x1, y1], fill=c + (255,))
    p = lambda x, y, c: d.point((x, y), fill=c + (255,))
    OUT, SK, HAIR, BLUE, BLUE2 = (24, 20, 32), (224, 172, 105), (92, 52, 24), (44, 84, 196), (28, 56, 140)
    BELT, PANT, BOOT, RED, RED2 = (112, 72, 32), (124, 84, 44), (36, 30, 30), (205, 35, 35), (150, 20, 28)
    r(23, 5, 40, 22, OUT); r(24, 6, 39, 21, SK)
    r(24, 6, 39, 10, HAIR); r(24, 11, 25, 14, HAIR); r(38, 11, 39, 13, HAIR)
    p(30, 11, HAIR); p(33, 11, HAIR); p(31, 10, HAIR)
    p(28, 14, OUT); p(35, 14, OUT); p(28, 15, (255, 255, 255))
    for x in (29, 30, 31):
        p(x, 17, (180, 100, 80))
    r(19, 23, 44, 41, OUT); r(20, 24, 43, 40, BLUE); r(20, 37, 43, 40, BLUE2)
    r(22, 29, 24, 30, BLUE2); p(40, 27, BLUE2)
    r(20, 33, 43, 35, BELT); r(30, 33, 33, 35, (230, 200, 60)); p(31, 34, BELT)
    r(20, 24, 43, 26, RED); r(20, 27, 22, 29, RED2); r(41, 27, 43, 28, RED2); p(26, 27, RED2)
    r(13, 23, 18, 39, OUT); r(14, 24, 17, 38, SK); r(45, 23, 50, 39, OUT); r(46, 24, 49, 38, SK)
    p(15, 30, (190, 140, 80)); p(47, 31, (190, 140, 80))
    r(21, 42, 30, 57, OUT); r(22, 42, 29, 56, PANT); r(34, 42, 43, 57, OUT); r(35, 42, 42, 56, PANT)
    p(25, 48, (90, 60, 30)); p(38, 50, (90, 60, 30))
    r(20, 56, 30, 61, OUT); r(21, 57, 29, 60, BOOT); r(34, 56, 44, 61, OUT); r(35, 57, 43, 60, BOOT)
    p(23, 58, (70, 60, 60)); p(37, 58, (70, 60, 60))
    return im


def fake_pixel_art(art, blur=0.8):
    """Art grid -> 512 px: 8x nearest upscale, then a slight Gaussian blur, like a generator's soft edges."""
    big = art.resize((art.width * 8, art.height * 8), Image.NEAREST).convert("RGB")
    return big.filter(ImageFilter.GaussianBlur(blur))


def ring_source(art, grow=5, colour=(250, 250, 246), blur=0.8):
    """The same figure with a near-white ring around it, `grow` = filter size (5 -> a 2 px ring at 512)."""
    big = art.resize((art.width * 8, art.height * 8), Image.NEAREST).convert("RGB")
    diff = ImageChops.difference(big, Image.new("RGB", big.size, MAG)).convert("L")
    mask = diff.point(lambda v: 255 if v else 0)
    ring_only = ImageChops.subtract(mask.filter(ImageFilter.MaxFilter(grow)), mask)
    big.paste(colour, mask=ring_only)
    return big.filter(ImageFilter.GaussianBlur(blur))


def white_figure():
    """A pale-armoured figure on transparency. Dark outline only on the left and bottom; the white armour
    touches the transparent background on the top and right, so a fringe clean-up floods the whole body."""
    im = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    r = lambda x0, y0, x1, y1, c: d.rectangle([x0, y0, x1, y1], fill=c + (255,))
    p = lambda x, y, c: d.point((x, y), fill=c + (255,))
    OUT, WH, WH2, GREY, EYE = (24, 22, 34), (245, 245, 248), (226, 228, 236), (150, 156, 170), (40, 40, 60)
    r(21, 6, 40, 24, WH); r(20, 6, 20, 24, OUT)                       # helmet, outline on the left only
    r(24, 13, 37, 15, EYE); p(30, 12, GREY); p(31, 12, GREY)
    r(17, 25, 44, 46, WH); r(16, 25, 16, 46, OUT)                     # torso
    r(19, 28, 21, 30, WH2); r(27, 33, 35, 35, GREY); p(40, 30, WH2); p(23, 40, WH2); p(38, 42, GREY)
    r(10, 26, 15, 44, WH); r(9, 26, 9, 44, OUT)                       # left arm
    r(45, 26, 50, 44, WH)                                             # right arm, no outline at all
    r(18, 47, 29, 60, WH); r(17, 47, 17, 60, OUT)                     # legs
    r(33, 47, 44, 60, WH); p(36, 52, WH2); p(21, 54, WH2)
    r(17, 61, 44, 61, OUT)                                            # outline under the feet
    return im


def two_figures():
    """Two separate figures of equal size on one 64 px canvas."""
    one = figure().crop((13, 5, 51, 62)).resize((19, 29), Image.NEAREST)   # 38x57 -> 19x29
    sheet = Image.new("RGBA", (64, 64), MAG + (255,))
    sheet.paste(one, (6, 18))
    sheet.paste(one, (39, 18))
    return sheet


def ringed_rgba():
    """The figure on transparency with a 1 art-pixel near-white halo around it and one enclosed light pixel
    (the eye glint at 28,15) that a fringe clean-up must leave alone."""
    art = figure()
    px = art.load()
    solid = Image.new("L", art.size, 0)
    sp = solid.load()
    for y in range(art.height):
        for x in range(art.width):
            if px[x, y][:3] != MAG:
                sp[x, y] = 255
    halo = ImageChops.subtract(solid.filter(ImageFilter.MaxFilter(3)), solid)
    out = Image.new("RGBA", art.size, (0, 0, 0, 0))
    out.paste(art, mask=solid)
    out.paste((248, 248, 244, 255), mask=halo)
    return out


def noisy_background_source():
    """The figure on a busy, non-flat background that unfake's flood fill cannot clear."""
    import random
    rnd = random.Random(3)
    art = figure()
    px = art.load()
    for y in range(art.height):
        for x in range(art.width):
            if px[x, y][:3] == MAG:
                v = rnd.randint(60, 200)
                px[x, y] = (v, (v * 3) % 200 + 30, (v * 7) % 200 + 30, 255)
    return art.resize((512, 512), Image.NEAREST).convert("RGB")


class MockComfy:
    """Just enough of ComfyUI's HTTP API for sprite_make: /system_stats, /prompt, /history/<id>, /view, /interrupt.
    Serves one fixed PNG as every job's output, or never finishes a job (complete=False) to test the time cap."""

    def __init__(self, png_bytes, complete=True):
        mock = self
        self.png, self.complete = png_bytes, complete
        self.prompts, self.interrupts = [], 0

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, code, body, ctype="application/json"):
                data = body if isinstance(body, bytes) else json.dumps(body).encode()
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                path = urlparse(self.path).path
                if path == "/system_stats":
                    self._send(200, {"devices": [{"name": "mock", "vram_free": 123456789}]})
                elif path.startswith("/history/"):
                    pid = path.rsplit("/", 1)[1]
                    if mock.complete and any(p[0] == pid for p in mock.prompts):
                        self._send(200, {pid: {"status": {"completed": True, "status_str": "success"},
                                               "outputs": {"9": {"images": [{"filename": "mock.png", "subfolder": "", "type": "output"}]}}}})
                    else:
                        self._send(200, {})
                elif path == "/view":
                    self._send(200, mock.png, "image/png")
                else:
                    self._send(404, {})

            def do_POST(self):
                n = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(n) if n else b""
                path = urlparse(self.path).path
                if path == "/prompt":
                    pid = f"job{len(mock.prompts) + 1}"
                    mock.prompts.append((pid, json.loads(body)["prompt"]))
                    self._send(200, {"prompt_id": pid, "number": len(mock.prompts)})
                elif path == "/interrupt":
                    mock.interrupts += 1
                    self._send(200, {})
                else:
                    self._send(404, {})

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


# ---------------------------------------------------------------- helpers

class Results:
    def __init__(self):
        self.rows = []

    def add(self, case, ok, detail):
        self.rows.append((case, ok, detail))
        print(f"  [{'PASS' if ok else 'FAIL'}] {case}: {detail}", flush=True)

    @property
    def ok(self):
        return all(ok for _, ok, _ in self.rows)


def run(args, timeout=TIMEOUT):
    t = time.time()
    p = subprocess.run([BASE_PY, str(SPRITE_MAKE)] + [str(a) for a in args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout, env=ENV)
    return p, time.time() - t


def load_report(out_dir, name):
    path = Path(out_dir) / f"{name}_report.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def opaque_pixels(im):
    return [(r, g, b) for r, g, b, a in im.convert("RGBA").getdata() if a >= 128]


def near_bg(px, bg=MAG, dist=90):
    return sum((a - b) ** 2 for a, b in zip(px, bg)) ** 0.5 < dist


def snapshot(root):
    """{path: (size, mtime_ns)} for every file under root, skipping .git folders."""
    snap = {}
    stack = [str(root)]
    while stack:
        cur = stack.pop()
        try:
            with os.scandir(cur) as it:
                for e in it:
                    if e.is_dir(follow_symlinks=False):
                        if e.name != ".git":
                            stack.append(e.path)
                    else:
                        st = e.stat(follow_symlinks=False)
                        snap[e.path] = (st.st_size, st.st_mtime_ns)
        except OSError:
            pass
    return snap


def aseprite_pids():
    p = subprocess.run(["tasklist", "/FI", "IMAGENAME eq Aseprite.exe", "/FO", "CSV", "/NH"],
                       capture_output=True, text=True, timeout=30)
    return {line.split('","')[1] for line in p.stdout.splitlines() if line.lower().startswith('"aseprite.exe"')}


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(path.parent))
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.path.pop(0)
    return mod


# ---------------------------------------------------------------- cases

def case_s1(res, tmp, out_root):
    src = tmp / "s1.png"
    fake_pixel_art(figure()).save(src)
    out = out_root / "S1"
    p, secs = run([out, "--name", "hero", "--from-image", src])
    rep = load_report(out, "hero")
    res.add("S1 exit 0", p.returncode == 0, f"exit {p.returncode} in {secs:.0f}s" + ("" if p.returncode == 0 else f"\n{p.stdout}\n{p.stderr}"))
    if not rep:
        res.add("S1 report", False, "no report written")
        return None
    grid = Image.open(out / "hero_grid.png").convert("RGBA")
    res.add("S1 grid <= 64 px long side", max(grid.size) <= 64, f"grid {grid.size[0]}x{grid.size[1]}")
    cols = set(opaque_pixels(grid))
    res.add("S1 <= 24 colours", len(cols) <= 24, f"{len(cols)} colours")
    a = grid.getchannel("A")
    corners = [grid.getpixel(xy)[3] for xy in ((0, 0), (grid.width - 1, 0), (0, grid.height - 1), (grid.width - 1, grid.height - 1))]
    magenta = sum(1 for c in opaque_pixels(grid) if near_bg(c))
    transparent = sum(1 for v in a.getdata() if v == 0) / (grid.width * grid.height)
    res.add("S1 transparent background", corners == [0, 0, 0, 0] and magenta == 0 and transparent > 0.4,
            f"corner alphas {corners}, {transparent:.0%} transparent, {magenta} magenta-ish opaque px")
    packed = {k: out / f"hero.{e}" for k, e in (("aseprite", "aseprite"), ("png", "png"), ("json", "json"))}
    res.add("S1 three packed files + report exist", all(v.is_file() and v.stat().st_size > 0 for v in packed.values())
            and (out / "hero_report.json").is_file() and (out / "hero_preview.png").is_file(),
            ", ".join(f"{k} {v.stat().st_size if v.is_file() else 'MISSING'}" for k, v in packed.items()))
    res.add("S1 report verdict pass", rep["verdict"] == "pass", f"verdict {rep['verdict']}, checks "
            + ", ".join(f"{k}={'ok' if c['pass'] else 'FAIL'}" for k, c in rep["checks"].items()))
    return rep


def case_s2(res, tmp, out_root):
    src = tmp / "s2.png"
    ring_source(figure()).save(src)
    out = out_root / "S2"
    p, secs = run([out, "--name", "hero", "--from-image", src])
    rep = load_report(out, "hero")
    res.add("S2 exit 0", p.returncode == 0, f"exit {p.returncode} in {secs:.0f}s" + ("" if p.returncode == 0 else f"\n{p.stdout}\n{p.stderr}"))
    d = (rep or {}).get("defringe") or {}
    res.add("S2 defringe applied, removed > 0", bool(d.get("applied")) and d.get("removed", 0) > 0, json.dumps(d))


def case_s3(res, tmp, out_root, ase):
    src = tmp / "s3.png"
    big = white_figure()
    big.resize((512, 512), Image.NEAREST).save(src)      # 8x, hard edges, binary alpha
    out = out_root / "S3"
    p, secs = run([out, "--name", "knight", "--from-image", src])
    rep = load_report(out, "knight")
    res.add("S3 ran", rep is not None and p.returncode in (0, 1), f"exit {p.returncode} in {secs:.0f}s" + ("" if rep else f"\n{p.stdout}\n{p.stderr}"))
    if not rep:
        return
    d = rep.get("defringe") or {}
    res.add("S3 defringe skipped with reason", d.get("applied") is False and str(d.get("skipped_reason", "")).startswith("defringe_skipped: would remove")
            and d.get("share", 0) > 0.03, json.dumps(d))
    grid = Image.open(out / "knight_grid.png").convert("RGBA")
    opq = opaque_pixels(grid)
    white = sum(1 for c in opq if min(c) > NEAR_WHITE)
    res.add("S3 white pixels still there", opq and white >= 0.4 * len(opq), f"{white} of {len(opq)} opaque px are near-white ({white / max(1, len(opq)):.0%})")
    _, would = ase.defringe_frame(grid, NEAR_WHITE)
    res.add("S3 ase_pack's own defringe WOULD eat > 3% of it", would > 0.03 * len(opq), f"{would} px = {would / max(1, len(opq)):.0%}")
    res.add("S3 exit 0", p.returncode == 0, f"exit {p.returncode}, checks " + ", ".join(f"{k}={'ok' if c['pass'] else 'FAIL'}" for k, c in rep["checks"].items()))


def case_s4(res, tmp, out_root):
    src = tmp / "s4.png"
    fake_pixel_art(two_figures()).save(src)
    out = out_root / "S4"
    p, secs = run([out, "--name", "pair", "--from-image", src])
    rep = load_report(out, "pair")
    res.add("S4 exit 1", p.returncode == 1, f"exit {p.returncode} in {secs:.0f}s" + ("" if p.returncode == 1 else f"\n{p.stdout}\n{p.stderr}"))
    if not rep:
        res.add("S4 report", False, "no report written")
        return
    failed = [k for k, c in rep["checks"].items() if not c["pass"]]
    res.add("S4 one-subject check is the one that failed", failed == ["one_subject"],
            f"failed checks {failed}; one_subject {rep['checks'].get('one_subject')}")
    res.add("S4 verdict fail, nothing packed", rep["verdict"] == "fail" and not (out / "pair.aseprite").exists(),
            f"verdict {rep['verdict']}, aseprite file present: {(out / 'pair.aseprite').exists()}")


def case_s5(res, out_root):
    out = out_root / "S5"
    p, secs = run([out, "--name", "x", "--brief", "x", "--server", "http://127.0.0.1:9"], timeout=60)
    res.add("S5 exit 3", p.returncode == 3, f"exit {p.returncode}")
    res.add("S5 message", "ComfyUI is not running; start ComfyUI Desktop and retry" in p.stderr, repr(p.stderr.strip()))
    res.add("S5 within 10 s", secs <= 10, f"{secs:.1f}s")


def case_s6(res, tmp, out_root):
    img = tmp / "s6.png"
    Image.new("RGB", (8, 8), MAG).save(img)
    p, _ = run([out_root / "S6a", "--name", "x", "--from-image", img, "--colors", 99], timeout=60)
    res.add("S6 --colors 99 -> exit 2", p.returncode == 2, f"exit {p.returncode}: {p.stderr.strip().splitlines()[-1] if p.stderr.strip() else ''}")
    p, _ = run([out_root / "S6b", "--name", "x", "--from-image", img, "--brief", "a thing"], timeout=60)
    res.add("S6 --brief + --from-image -> exit 2", p.returncode == 2, f"exit {p.returncode}: {p.stderr.strip().splitlines()[-1] if p.stderr.strip() else ''}")


def case_x1(res, sm, ase):
    """sprite_make.defringe_frame must be ase_pack.defringe_frame's algorithm: compare on varied RGBA images."""
    cases = {"white_figure": white_figure(), "halo": ringed_rgba()}
    ok, notes = True, []
    for name, im in cases.items():
        for n in (180, 100, 240):
            a, ra = ase.defringe_frame(im, n)
            b, rb = sm.defringe_frame(im, n)
            same = ra == rb and list(a.getdata()) == list(b.getdata())
            ok &= same
            notes.append(f"{name}@{n}: {ra}/{rb}{'' if same else ' DIFFER'}")
    halo_removed = ase.defringe_frame(ringed_rgba(), 180)[1]
    res.add("X1 defringe_frame matches ase_pack's", ok and halo_removed > 0, "; ".join(notes))


def case_x3(res, tmp, out_root, sm):
    png = io.BytesIO()
    fake_pixel_art(figure()).save(png, "PNG")
    brief = "young adventurer with short brown hair, blue tunic"
    # 3a: sd15pixel through the mock
    mock = MockComfy(png.getvalue())
    try:
        out = out_root / "X3a"
        p, secs = run([out, "--name", "mock", "--brief", brief, "--view", "front", "--model", "sd15pixel", "--seed", 5,
                       "--server", mock.url])
        rep = load_report(out, "mock") or {}
        graph = mock.prompts[0][1] if mock.prompts else {}
        pos = graph.get("6", {}).get("inputs", {}).get("text", "")
        res.add("X3a brief -> mock ComfyUI -> pass", p.returncode == 0 and rep.get("verdict") == "pass",
                f"exit {p.returncode} in {secs:.0f}s, {len(mock.prompts)} job(s)" + ("" if p.returncode == 0 else f"\n{p.stdout}\n{p.stderr}"))
        res.add("X3a graph and prompt as specified",
                graph.get("4", {}).get("inputs", {}).get("ckpt_name") == "dreamshaperPixelart_v10.safetensors"
                and graph.get("3", {}).get("inputs", {}).get("seed") == 5 and graph.get("5", {}).get("inputs", {}).get("width") == 512
                and brief in pos and "front view" in pos and "no scenery" in pos and "solid single-color background" in pos,
                f"ckpt {graph.get('4', {}).get('inputs', {}).get('ckpt_name')}, seed {graph.get('3', {}).get('inputs', {}).get('seed')}, prompt: {pos[:110]}...")
        res.add("X3a report: model, licence note, server, vram, seed",
                rep.get("model") == "sd15pixel" and "UNVERIFIED" in rep.get("licence_note", "") and rep.get("server") == mock.url
                and rep.get("vram_free_bytes_before") == 123456789 and rep["attempts"][0]["seed"] == 5 and "generate" in rep["attempts"][0]["seconds"],
                f"licence: {rep.get('licence_note')}; vram {rep.get('vram_free_bytes_before')}; seconds {rep['attempts'][0]['seconds'] if rep.get('attempts') else None}")
    finally:
        mock.close()
    # 3b: the time cap -> POST /interrupt -> failed attempts with consecutive seeds
    mock = MockComfy(png.getvalue(), complete=False)
    try:
        out = out_root / "X3b"
        p, secs = run([out, "--name", "slow", "--brief", brief, "--model", "sd15pixel", "--seed", 7, "--retries", 2,
                       "--timeout", 3, "--server", mock.url], timeout=120)
        rep = load_report(out, "slow") or {}
        atts = rep.get("attempts", [])
        res.add("X3b time cap: exit 1, 2 attempts, seeds 7 and 8, one interrupt each",
                p.returncode == 1 and [a["seed"] for a in atts] == [7, 8] and mock.interrupts == 2
                and all("time cap" in (a.get("error") or "") for a in atts) and rep.get("verdict") == "fail",
                f"exit {p.returncode} in {secs:.0f}s, interrupts {mock.interrupts}, errors {[a.get('error') for a in atts]}")
    finally:
        mock.close()
    # 3c: qwen: template graph patched, exactly one attempt, 600 s default cap recorded
    mock = MockComfy(png.getvalue())
    try:
        out = out_root / "X3c"
        p, secs = run([out, "--name", "q", "--brief", brief, "--model", "qwen", "--seed", 11, "--retries", 3, "--server", mock.url])
        rep = load_report(out, "q") or {}
        graph = mock.prompts[0][1] if mock.prompts else {}
        res.add("X3c qwen: template patched, one attempt, 600 s cap",
                p.returncode == 0 and len(rep.get("attempts", [])) == 1 and rep["params"]["timeout"] == 600
                and brief in graph.get("5", {}).get("inputs", {}).get("text", "") and graph.get("8", {}).get("inputs", {}).get("seed") == 11,
                f"exit {p.returncode}, attempts {len(rep.get('attempts', []))}, cap {rep.get('params', {}).get('timeout')}")
    finally:
        mock.close()
    # 3d: sdxl-pixel needs the LoRA on disk; it is not downloaded for you
    if not sm.LORA_PATH.is_file():
        p, _ = run([out_root / "X3d", "--name", "x", "--brief", brief, "--model", "sdxl-pixel", "--server", "http://127.0.0.1:9"], timeout=60)
        res.add("X3d sdxl-pixel without its LoRA on disk -> exit 2", p.returncode == 2, f"exit {p.returncode}: {p.stderr.strip().splitlines()[-1] if p.stderr.strip() else ''}")
    # the sdxl-pixel graph itself (no server needed): LoRA node wired into both the sampler and both text encoders
    g = sm.build_graph("sdxl-pixel", "p", 1)
    wired = (g["10"]["class_type"] == "LoraLoader" and g["3"]["inputs"]["model"] == ["10", 0]
             and g["6"]["inputs"]["clip"] == ["10", 1] and g["7"]["inputs"]["clip"] == ["10", 1]
             and g["4"]["inputs"]["ckpt_name"] == "sd_xl_base_1.0.safetensors" and g["5"]["inputs"]["width"] == 1024)
    res.add("X3d sdxl-pixel graph wires the LoRA in", wired, "LoraLoader node 10 -> KSampler model, CLIP encoders")


def case_x4(res, tmp, out_root):
    src = tmp / "x4.png"
    noisy_background_source().save(src)
    out = out_root / "X4"
    p, secs = run([out, "--name", "busy", "--from-image", src, "--server", "http://127.0.0.1:9"])
    rep = load_report(out, "busy") or {}
    chk = rep.get("checks", {}).get("background_removed", {})
    notes = " ".join((rep.get("attempts") or [{}])[0].get("notes", []))
    res.add("X4 unremovable background fails honestly", p.returncode == 1 and chk.get("pass") is False and "not reachable" in notes,
            f"exit {p.returncode}, opaque share {chk.get('opaque_share')}, notes: {notes[:160]}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--only", help="comma list of cases to run, e.g. S1,S4 (the full run is the acceptance run)")
    args = ap.parse_args()
    want = set(args.only.split(",")) if args.only else {"S1", "S2", "S3", "S4", "S5", "S6", "X1", "X3", "X4"}

    out_root = OUT_ROOT / time.strftime("run_%Y%m%d_%H%M%S")
    out_root.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="sprite_make_selftest_"))
    res = Results()
    before = snapshot(SKILLS_ROOT)
    pids_before = aseprite_pids()
    print(f"sprite_make self-test; outputs in {out_root}", flush=True)
    try:
        ase = load_module(ASE_PACK, "ase_pack_ref")
        sm = load_module(SPRITE_MAKE, "sprite_make_ref")
        if "S1" in want:
            case_s1(res, tmp, out_root)
        if "S2" in want:
            case_s2(res, tmp, out_root)
        if "S3" in want:
            case_s3(res, tmp, out_root, ase)
        if "S4" in want:
            case_s4(res, tmp, out_root)
        if "S5" in want:
            case_s5(res, out_root)
        if "S6" in want:
            case_s6(res, tmp, out_root)
        if "X1" in want:
            case_x1(res, sm, ase)
        if "X3" in want:
            case_x3(res, tmp, out_root, sm)
        if "X4" in want:
            case_x4(res, tmp, out_root)
        after = snapshot(SKILLS_ROOT)
        changed = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k) and Path(k).resolve() not in OWN_FILES)
        res.add("X2 nothing in sarges-skills changed except the two scripts", not changed,
                f"{len(after)} files checked" + ("" if not changed else "; changed: " + ", ".join(changed[:10])))
        left = aseprite_pids() - pids_before
        res.add("X2 no Aseprite process left running", not left, f"new Aseprite pids: {sorted(left) or 'none'}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    passed = sum(1 for _, ok, _ in res.rows if ok)
    print(f"\n{passed}/{len(res.rows)} checks passed -> {'ALL PASS' if res.ok else 'FAILED'}")
    return 0 if res.ok else 1


if __name__ == "__main__":
    sys.exit(main())
