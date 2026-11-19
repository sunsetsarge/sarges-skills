"""One command, one still sprite: a text brief (or an existing image) in, a checked
and packed sprite out, no human steps in between.

  generate (ComfyUI) -> pixelize (grid snap + palette lock + transparent background)
                     -> guarded fringe clean -> checks -> pack with ase_pack.py

Runs under the base interpreter (C:\\AI-Shared\\python.exe: Pillow + requests).
Shells out to pixelize.py, qc_check.py (venv-unfake interpreter), art_qc.py and
game-asset-pipeline's ase_pack.py, so the same tools a person would run are the
ones that decide pass or fail. Never starts, stops or configures ComfyUI; the
only thing it ever sends besides its own jobs is POST /interrupt for a job of its
own that hit the time cap.

Usage:
  sprite_make.py OUT_DIR --name NAME (--brief "TEXT" | --from-image PNG)
                 [--model sdxl|sd15pixel|qwen|sdxl-pixel] [--size N] [--colors N]
                 [--view front|side|top-down] [--seed N] [--retries N]
                 [--timeout SEC] [--server URL] [--no-defringe] [--keep-work]

Exit codes: 0 pass, 1 fail, 2 bad arguments, 3 ComfyUI unreachable (brief given).

Outputs in OUT_DIR:
  NAME.aseprite / NAME.png / NAME.json   packed by ase_pack.py (pass only)
  NAME_grid.png                           the native-resolution sprite
  NAME_preview.png                        the sprite at 8x on #466e50, for a human
  NAME_report.json                        brief, model, licence note, per-attempt seed,
                                          seconds per stage, every check, final verdict
  _attempts/attemptN/                     the best attempt's files (all with --keep-work)

Known upstream quirks this script works around (measured 2026-11-19):
  1. pixeloe_worker pads a FULL extra cell when the source size is an exact multiple of
     its cell size, so a 512 px source becomes a 65 px grid shifted half a cell. When the
     overhang is at most one cell, the source copy is trimmed on the right/bottom so the
     grid comes out at exactly N and aligned.
  2. unfake's auto scale detection falls back to edge_aware_detect whenever
     runs_based_detect says 1, and edge_aware_detect false-positives on near-1x pixel
     art (qc_check.py documents the same trap), collapsing a 64 px sprite to ~10 px.
     When runs_based_detect says 1 on pixelize's own pixeloe intermediate, unfake is re-run
     once on that intermediate at scale 1 (the manual-scale fallback pixelize.py itself uses
     for its own degenerate case), with a wider flood-fill tolerance: at the default tolerance
     of 1 the flat background keeps magenta specks after pixeloe's colour noise.
"""
import sys
sys.dont_write_bytecode = True   # never leave .pyc files in the skill folders

import argparse
import json
import os
import random
import re
import shutil
import subprocess
import time
import uuid
from collections import deque
from pathlib import Path

import requests
from PIL import Image

SCRIPTS = Path(__file__).resolve().parent
SKILL_DIR = SCRIPTS.parent
SKILLS_ROOT = SKILL_DIR.parent
sys.path.insert(0, str(SCRIPTS))
import pixelize                      # noqa: E402  (paths, nearest_upscale, VENV_UNFAKE_CLI)
from comfy_submit import build_workflow   # noqa: E402  (the plain checkpoint txt2img graph)

BASE_PY = r"C:\AI-Shared\python.exe"
VENV_UNFAKE_PY = SKILL_DIR / "venv-unfake" / "Scripts" / "python.exe"
PIXELIZE = SCRIPTS / "pixelize.py"
QC_CHECK = SCRIPTS / "qc_check.py"
ART_QC = SCRIPTS / "art_qc.py"
COMFY_RMBG = SCRIPTS / "comfy_rmbg.py"
ASE_PACK = SKILLS_ROOT / "game-asset-pipeline" / "scripts" / "lane-2d" / "ase_pack.py"
QWEN_TEMPLATE = SKILL_DIR / "assets" / "workflows" / "lane-a-qwen.json"
LORA_NAME = "pixel-art-xl.safetensors"
LORA_PATH = Path(r"E:\AI\Models\loras") / LORA_NAME

PROBE_URLS = ("http://127.0.0.1:8188", "http://127.0.0.1:8000")
NOT_RUNNING_MSG = "ComfyUI is not running; start ComfyUI Desktop and retry"
DEFRINGE_THRESHOLD = 180
BG_TOLERANCE = 16                  # unfake flood-fill tolerance per channel for the finalise pass
DEFRINGE_MAX_SHARE = 0.03          # skip the fringe clean if it would remove more than this
OPAQUE_BACKGROUND_SHARE = 0.60     # more opaque than this = the background was not removed
ONE_SUBJECT_SHARE = 0.85
FILL_RANGE = (0.35, 0.98)
MAX_EDGES_TOUCHED = 2
MIN_GRID_SHARE = 0.30              # grid long side must be at least this share of --size
PREVIEW_SCALE = 8
PREVIEW_BG = (0x46, 0x6e, 0x50)
SUBPROC_ENV = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8"}

NEGATIVE = ("blurry, anti-aliased, smooth gradient, photorealistic, 3d render, text, watermark, "
            "soft shading, jpeg artifacts, scenic background, complex background, multiple "
            "characters, sprite sheet, cropped, cut off")
VIEW_PHRASE = {
    "front": "front view, facing the camera, standing pose",
    "side": "side view, full profile, standing",
    "top-down": "top-down view, seen from directly above, overhead",
}

MODELS = {
    "sdxl": {
        "kind": "checkpoint", "ckpt": "sd_xl_base_1.0.safetensors", "width": 1024, "height": 1024,
        "steps": 25, "cfg": 7.0, "sampler": "dpmpp_2m", "scheduler": "karras", "timeout": 300,
        "licence": "SDXL base 1.0 (CreativeML OpenRAIL++-M): licence-clean per Local_Sprite_Lab PLAN section 3.",
    },
    "sd15pixel": {
        "kind": "checkpoint", "ckpt": "dreamshaperPixelart_v10.safetensors", "width": 512, "height": 512,
        "steps": 25, "cfg": 7.0, "sampler": "dpmpp_2m", "scheduler": "karras", "timeout": 300,
        "licence": "dreamshaperPixelart_v10: LICENCE UNVERIFIED. PROTOTYPE ONLY, do not ship output from this model.",
    },
    "sdxl-pixel": {
        "kind": "checkpoint+lora", "ckpt": "sd_xl_base_1.0.safetensors", "width": 1024, "height": 1024,
        "steps": 25, "cfg": 7.0, "sampler": "dpmpp_2m", "scheduler": "karras", "timeout": 300,
        "licence": "SDXL base 1.0 (OpenRAIL++-M) + pixel-art-xl LoRA at 1.0: LoRA licence not verified; check before shipping.",
    },
    "qwen": {
        "kind": "template", "template": QWEN_TEMPLATE, "prompt_node": "5", "seed_node": "8", "timeout": 600,
        "licence": "Qwen-Image (Apache-2.0) per Local_Sprite_Lab PLAN section 3; Lightning LoRA licence not verified.",
    },
}


class Fail(Exception):
    """An attempt-level failure with a user-facing reason."""


# ---------------------------------------------------------------- server

def probe_server(url, timeout=3):
    """-> (url, system_stats dict) when ComfyUI answers /system_stats, else None."""
    url = url.rstrip("/")
    try:
        r = requests.get(f"{url}/system_stats", timeout=timeout)
        if r.status_code == 200:
            return url, r.json()
    except (requests.RequestException, ValueError):
        pass
    return None


def resolve_server(explicit):
    """--server URL, else env COMFYUI_URL, else probe :8188 then :8000. -> (url, stats) or None."""
    explicit = explicit or os.environ.get("COMFYUI_URL")
    if explicit:
        return probe_server(explicit)
    for url in PROBE_URLS:
        hit = probe_server(url)
        if hit:
            return hit
    return None


def vram_free(stats):
    try:
        return int(stats["devices"][0]["vram_free"])
    except (KeyError, IndexError, TypeError, ValueError):
        return None


# ---------------------------------------------------------------- generation

def build_prompt(brief, view):
    return (f"pixel art, {brief}, {VIEW_PHRASE[view]}, full body, 16-bit SNES RPG sprite style, "
            "flat colors, no anti-aliasing, crisp pixel grid, hard edges, solid single-color "
            "background, no scenery, studio background, single subject, game asset")


def build_graph(model, prompt, seed):
    spec = MODELS[model]
    if spec["kind"] == "template":
        wf = json.loads(Path(spec["template"]).read_text(encoding="utf-8"))
        wf[spec["prompt_node"]]["inputs"]["text"] = prompt
        wf[spec["seed_node"]]["inputs"]["seed"] = seed
        return wf
    wf = build_workflow(spec["ckpt"], prompt, NEGATIVE, spec["width"], spec["height"],
                        spec["steps"], spec["cfg"], spec["sampler"], spec["scheduler"], seed)
    if spec["kind"] == "checkpoint+lora":
        wf["10"] = {"class_type": "LoraLoader",
                    "inputs": {"model": ["4", 0], "clip": ["4", 1], "lora_name": LORA_NAME,
                               "strength_model": 1.0, "strength_clip": 1.0}}
        wf["3"]["inputs"]["model"] = ["10", 0]
        wf["6"]["inputs"]["clip"] = ["10", 1]
        wf["7"]["inputs"]["clip"] = ["10", 1]
    return wf


def run_comfy_job(server, workflow, cap, out_path):
    """Submit one job, wait at most `cap` seconds, save the first output image to out_path.
    On the cap: POST /interrupt (for this job only) and raise Fail."""
    r = requests.post(f"{server}/prompt", json={"prompt": workflow, "client_id": str(uuid.uuid4())},
                      timeout=30)
    if r.status_code != 200:
        raise Fail(f"ComfyUI rejected the workflow: HTTP {r.status_code} {r.text[:300]}")
    prompt_id = r.json()["prompt_id"]
    start = time.time()
    entry = None
    while entry is None:
        if time.time() - start > cap:
            try:
                requests.post(f"{server}/interrupt", timeout=10)
            except requests.RequestException:
                pass
            raise Fail(f"generation hit the {cap}s time cap; interrupted job {prompt_id}")
        try:
            hist = requests.get(f"{server}/history/{prompt_id}", timeout=10).json()
        except (requests.RequestException, ValueError):
            hist = {}
        got = hist.get(prompt_id)
        if got:
            status = got.get("status", {})
            if status.get("status_str") == "error":
                raise Fail(f"ComfyUI job failed: {json.dumps(status)[:400]}")
            if status.get("completed"):
                entry = got
                break
        time.sleep(2)
    for node_out in entry.get("outputs", {}).values():
        for img in node_out.get("images", []):
            params = {"filename": img["filename"], "subfolder": img.get("subfolder", ""),
                      "type": img.get("type", "output")}
            v = requests.get(f"{server}/view", params=params, timeout=60)
            v.raise_for_status()
            Path(out_path).write_bytes(v.content)
            Image.open(out_path).verify()
            return Path(out_path)
    raise Fail("no image found in the job outputs")


def run_rmbg(server, source, out_path, cap=300):
    """comfy_rmbg.py's own functions, pointed at `server` (its module-level SERVER is hard-coded
    to port 8000). Runs the same RMBG workflow comfy_rmbg.main() runs."""
    import comfy_rmbg
    import comfy_submit
    comfy_submit.SERVER = server
    comfy_rmbg.SERVER = server
    name = comfy_rmbg.upload_image(Path(source))
    wf = json.loads(Path(comfy_rmbg.WORKFLOW).read_text(encoding="utf-8"))
    wf["1"]["inputs"]["image"] = name
    wf["2"]["inputs"]["model"] = "INSPYRENET"
    return run_comfy_job(server, wf, cap, out_path)


# ---------------------------------------------------------------- image helpers

def opaque_count(im):
    return sum(1 for a in im.getchannel("A").getdata() if a > 0)


def opaque_share(im):
    n = im.width * im.height
    return opaque_count(im) / n if n else 0.0


def count_colors(im):
    cols = set()
    for r, g, b, a in im.getdata():
        if a >= 128:
            cols.add((r, g, b))
    return len(cols)


def defringe_frame(im, n):
    """Same algorithm as game-asset-pipeline lane-2d ase_pack.py defringe_frame (the self-test
    proves they agree): light = alpha > 0 and min(R,G,B) > n; flood from every alpha-0 pixel
    (8-connectivity) entering only light pixels; each one reached becomes (0,0,0,0).
    Enclosed light pixels stay. -> (image, pixels removed)."""
    w, h = im.size
    data = list(im.getdata())
    seeds = [i for i, p in enumerate(data) if p[3] == 0]
    if not seeds:
        return im, 0
    light = bytearray(1 if p[3] > 0 and min(p[:3]) > n else 0 for p in data)
    q = deque(seeds)
    removed = 0
    while q:
        i = q.popleft()
        x, y = i % w, i // w
        for ny in range(max(0, y - 1), min(h, y + 2)):
            for nx in range(max(0, x - 1), min(w, x + 2)):
                j = ny * w + nx
                if light[j]:
                    light[j] = 0
                    data[j] = (0, 0, 0, 0)
                    removed += 1
                    q.append(j)
    if not removed:
        return im, 0
    out = Image.new("RGBA", im.size)
    out.putdata(data)
    return out, removed


def blobs(im, thr=128):
    """Sizes of the 8-connected opaque blobs (alpha >= thr), largest first."""
    w, h = im.size
    alpha = list(im.getchannel("A").getdata())
    seen = bytearray(w * h)
    sizes = []
    for start in range(w * h):
        if alpha[start] < thr or seen[start]:
            continue
        seen[start] = 1
        q = deque([start])
        n = 0
        while q:
            i = q.popleft()
            n += 1
            x, y = i % w, i // w
            for ny in range(max(0, y - 1), min(h, y + 2)):
                for nx in range(max(0, x - 1), min(w, x + 2)):
                    j = ny * w + nx
                    if alpha[j] >= thr and not seen[j]:
                        seen[j] = 1
                        q.append(j)
        sizes.append(n)
    return sorted(sizes, reverse=True)


def edges_touched(im, thr=128):
    w, h = im.size
    a = im.getchannel("A").point(lambda v: 255 if v >= thr else 0)
    touched = []
    if a.crop((0, 0, 1, h)).getbbox():
        touched.append("left")
    if a.crop((w - 1, 0, w, h)).getbbox():
        touched.append("right")
    if a.crop((0, 0, w, 1)).getbbox():
        touched.append("top")
    if a.crop((0, h - 1, w, h)).getbbox():
        touched.append("bottom")
    return touched


def prepare_source(src, dst, size):
    """Copy src -> dst for pixelize.py. Two fixes for pixeloe_worker quirks:
    - a source smaller than 2 cells per target pixel crashes it (stride 0), so it is first enlarged by an
      integer nearest-neighbour factor;
    - a one-cell overhang is trimmed (quirk 1 in the docstring).
    -> (target_size to pass to pixelize, note or None)."""
    im = Image.open(src)
    note = None
    w, h = im.size
    if min(w, h) // size < 2:
        k = -(-2 * size // min(w, h))
        im = im.resize((w * k, h * k), Image.NEAREST)
        note = f"source {w}x{h} enlarged {k}x (nearest) so pixeloe has at least 2 px per art pixel"
        w, h = im.size
    ps = min(w, h) // size
    keep = size * ps - 1
    nw = keep if 0 < w - keep <= ps else w
    nh = keep if 0 < h - keep <= ps else h
    if (nw, nh) != (w, h):
        target = min(nw, nh) // ps
        if target >= 1 and min(nw, nh) // target == ps:
            im.crop((0, 0, nw, nh)).save(dst)
            trim = f"source trimmed {w}x{h} -> {nw}x{nh}, pixelize target-size {target} (cell {ps}px)"
            return target, f"{note}; {trim}" if note else trim
    im.save(dst)
    return size, note


# ---------------------------------------------------------------- stages

def sh(cmd, timeout, cwd=None):
    """Run a subprocess with a timeout; -> CompletedProcess (never raises on non-zero exit)."""
    try:
        return subprocess.run([str(c) for c in cmd], capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=timeout, env=SUBPROC_ENV, cwd=cwd)
    except subprocess.TimeoutExpired as e:
        raise Fail(f"{Path(str(cmd[1])).name} did not finish within {timeout}s and was stopped")


def tail(text, n=600):
    text = (text or "").strip()
    return text[-n:]


def detect_scales(path):
    """(runs_based_detect, edge_aware_detect) of an image, in the venv-unfake interpreter."""
    p = sh([VENV_UNFAKE_PY, "-c",
            "import unfake, numpy as np, sys; from PIL import Image; "
            "img = np.array(Image.open(sys.argv[1]).convert('RGBA')); "
            "print(unfake.runs_based_detect(img), unfake.edge_aware_detect(img))", path], timeout=120)
    try:
        runs, edge = p.stdout.strip().splitlines()[-1].split()
        return int(runs), int(edge)
    except (ValueError, IndexError):
        raise Fail(f"scale detection failed: {tail(p.stderr)}")


def run_pixelize(src, attempt_dir, name, size, colors, notes):
    """prepare the source, run pixelize.py, then finalise at scale 1 when pixeloe's grid has no block pattern."""
    prepared = attempt_dir / f"{name}_src.png"
    target, note = prepare_source(src, prepared, size)
    if note:
        notes.append(note)
    p = sh([BASE_PY, PIXELIZE, prepared, "-o", attempt_dir, "--name", name, "--method", "pixeloe",
            "--target-size", target, "--colors", colors, "--alpha"], timeout=900)
    grid = attempt_dir / f"{name}_grid.png"
    if p.returncode != 0 or not grid.exists():
        raise Fail(f"pixelize.py failed (exit {p.returncode}): {tail(p.stderr)}")
    pe = attempt_dir / f"{name}_pixeloe.png"
    final = attempt_dir / f"{name}_final.png"
    gsz, psz = Image.open(grid).size, Image.open(pe).size
    runs, edge = detect_scales(pe)
    if runs == 1:
        # pixeloe's output has no real block structure, so scale 1 is correct whatever edge_aware_detect
        # says (quirk 2). Finalise it with unfake at scale 1 and a background tolerance wide enough for
        # the colour noise pixeloe leaves in a flat background (the tolerance-1 default left magenta specks).
        u = sh([pixelize.VENV_UNFAKE_CLI, pe, "-o", grid, "-c", colors, "--cleanup", "morph,jaggy",
                "--transparent-background", "--background-tolerance", BG_TOLERANCE, "-s", 1], timeout=300)
        if u.returncode != 0:
            raise Fail(f"unfake scale-1 finalise failed (exit {u.returncode}): {tail(u.stderr)}")
        pixelize.nearest_upscale(grid, final, 512)
        im = Image.open(grid).convert("RGBA")
        pal = sorted({"#%02x%02x%02x" % c[:3] for c in im.getdata() if c[3] >= 128})
        (attempt_dir / f"{name}_palette.json").write_text(json.dumps({"colors": pal, "count": len(pal)}, indent=2))
        notes.append(f"pixelize.py grid {gsz} (pixeloe intermediate {psz}, runs_based={runs}, edge_aware={edge}); "
                     f"unfake re-run at scale 1, background tolerance {BG_TOLERANCE} -> {im.size}")
    else:
        notes.append(f"pixelize.py grid {gsz} kept: runs_based_detect={runs} on the pixeloe intermediate "
                     f"{psz} reports a real block pattern")
    return grid, final


def guarded_defringe(grid, final, enabled):
    """-> report dict. Rewrites grid + final only when the clean-up is applied."""
    if not enabled:
        return {"applied": False, "removed": 0, "threshold": DEFRINGE_THRESHOLD, "skipped_reason": "disabled by --no-defringe"}
    im = Image.open(grid).convert("RGBA")
    total = opaque_count(im)
    cleaned, removed = defringe_frame(im, DEFRINGE_THRESHOLD)
    rep = {"applied": False, "removed": 0, "threshold": DEFRINGE_THRESHOLD, "opaque_before": total}
    if removed == 0:
        rep["skipped_reason"] = "nothing to remove"
    elif removed > DEFRINGE_MAX_SHARE * total:
        rep["skipped_reason"] = f"defringe_skipped: would remove {removed} px"
        rep["would_remove"] = removed
        rep["share"] = round(removed / total, 4)
    else:
        cleaned.save(grid)
        pixelize.nearest_upscale(grid, final, 512)
        rep.update(applied=True, removed=removed, share=round(removed / total, 4))
    return rep


def run_checks(grid, final, size, colors, bg_resolved):
    """-> dict name -> {pass, ...numbers}. Every check is programmatic."""
    checks = {}
    im = Image.open(grid).convert("RGBA")
    w, h = im.size
    share = opaque_share(im)
    checks["background_removed"] = {"pass": share <= OPAQUE_BACKGROUND_SHARE and bg_resolved,
                                    "opaque_share": round(share, 4), "limit": OPAQUE_BACKGROUND_SHARE}
    checks["grid_resolution"] = {"pass": max(w, h) >= MIN_GRID_SHARE * size, "grid": [w, h],
                                 "min_long_side": round(MIN_GRID_SHARE * size, 1)}
    ncol = count_colors(im)
    checks["colors_within_cap"] = {"pass": ncol <= colors, "colors": ncol, "cap": colors}

    p = sh([VENV_UNFAKE_PY, QC_CHECK, grid], timeout=180)       # default cap 32
    qc = {}
    qc_json = grid.with_name(grid.stem.replace("_grid", "") + "_qc.json")
    if qc_json.exists():
        try:
            qc = json.loads(qc_json.read_text(encoding="utf-8"))
        except ValueError:
            qc = {}
    checks["qc_check"] = {"pass": p.returncode == 0, "exit": p.returncode,
                          "detail": {k: qc[k] for k in ("true_grid", "color_count", "alpha_clean", "crisp_upscale") if k in qc}
                          or tail(p.stdout + p.stderr)}

    p = sh([BASE_PY, ART_QC, "sprite", grid], timeout=180)
    aq = {}
    aq_json = grid.with_name(grid.stem + "_artqc.json")
    if aq_json.exists():
        try:
            aq = json.loads(aq_json.read_text(encoding="utf-8"))
        except ValueError:
            aq = {}
    checks["art_qc"] = {"pass": p.returncode == 0, "exit": p.returncode,
                        "metrics": {k: v.get("value") for k, v in aq.get("metrics", {}).items()}}

    sizes = blobs(im)
    total = sum(sizes)
    largest = sizes[0] / total if total else 0.0
    checks["one_subject"] = {"pass": bool(total) and largest >= ONE_SUBJECT_SHARE, "blobs": len(sizes),
                             "largest_share": round(largest, 4), "min_share": ONE_SUBJECT_SHARE}
    bbox = im.getchannel("A").point(lambda a: 255 if a >= 128 else 0).getbbox()
    fill = (max(bbox[2] - bbox[0], bbox[3] - bbox[1]) / max(w, h)) if bbox else 0.0
    checks["subject_fill"] = {"pass": FILL_RANGE[0] <= fill <= FILL_RANGE[1], "fill": round(fill, 4),
                              "range": list(FILL_RANGE), "bbox": list(bbox) if bbox else None}
    touched = edges_touched(im)
    checks["frame_edges"] = {"pass": len(touched) <= MAX_EDGES_TOUCHED, "touched": touched,
                             "max_edges": MAX_EDGES_TOUCHED}
    return checks


def make_preview(grid, out_path):
    im = Image.open(grid).convert("RGBA")
    big = im.resize((im.width * PREVIEW_SCALE, im.height * PREVIEW_SCALE), Image.NEAREST)
    bg = Image.new("RGBA", big.size, PREVIEW_BG + (255,))
    bg.alpha_composite(big)
    bg.convert("RGB").save(out_path)


def pack(grid, out_dir, name, colors):
    p = sh([BASE_PY, ASE_PACK, out_dir, "--name", name, "--frames", grid, "--max-colors", colors,
            "--pivot", "bottom-center"], timeout=240)
    outs = {k: str(Path(out_dir) / f"{name}.{ext}") for k, ext in (("aseprite", "aseprite"), ("sheet", "png"), ("json", "json"))}
    ok = p.returncode == 0 and all(os.path.isfile(v) and os.path.getsize(v) > 0 for v in outs.values())
    return ok, outs, tail(p.stdout + p.stderr, 800)


# ---------------------------------------------------------------- attempt loop

def one_attempt(args, n, seed, attempt_dir, server, prompt, spec, source_img):
    """-> attempt record dict. Never raises: a failure is recorded, not thrown."""
    rec = {"attempt": n, "seed": seed, "seconds": {}, "notes": [], "checks": {}, "defringe": None,
           "passed": False, "error": None, "dir": str(attempt_dir)}
    attempt_dir.mkdir(parents=True, exist_ok=True)
    name = args.name
    t = time.perf_counter()
    try:
        if args.brief:
            src = attempt_dir / "source.png"
            cap = args.timeout or spec["timeout"]
            run_comfy_job(server, build_graph(args.model, prompt, seed), cap, src)
            rec["seconds"]["generate"] = round(time.perf_counter() - t, 1)
        else:
            src = attempt_dir / "source.png"
            Image.open(source_img).convert("RGBA").save(src)
        t = time.perf_counter()
        grid, final = run_pixelize(src, attempt_dir, name, args.size, args.colors, rec["notes"])
        rec["seconds"]["pixelize"] = round(time.perf_counter() - t, 1)

        bg_resolved = True
        if opaque_share(Image.open(grid).convert("RGBA")) > OPAQUE_BACKGROUND_SHARE:
            t = time.perf_counter()
            hit = server if server else (resolve_server(args.server) or (None,))[0]
            if not hit:
                bg_resolved = False
                rec["notes"].append("background still opaque and ComfyUI is not reachable for comfy_rmbg.py")
            else:
                try:
                    nobg = run_rmbg(hit, src, attempt_dir / "source_nobg.png")
                    grid, final = run_pixelize(nobg, attempt_dir, name, args.size, args.colors, rec["notes"])
                    rec["notes"].append("comfy_rmbg.py (INSPYRENET) run on the source, then pixelize.py again")
                except (Fail, requests.RequestException) as e:
                    bg_resolved = False
                    rec["notes"].append(f"comfy_rmbg.py failed: {e}")
            rec["seconds"]["rmbg"] = round(time.perf_counter() - t, 1)

        t = time.perf_counter()
        rec["defringe"] = guarded_defringe(grid, final, not args.no_defringe)
        rec["seconds"]["defringe"] = round(time.perf_counter() - t, 1)

        t = time.perf_counter()
        rec["checks"] = run_checks(grid, final, args.size, args.colors, bg_resolved)
        rec["seconds"]["checks"] = round(time.perf_counter() - t, 1)
        rec["grid"] = str(grid)
        rec["grid_size"] = list(Image.open(grid).size)
        rec["passed"] = all(c["pass"] for c in rec["checks"].values())
    except Fail as e:
        rec["error"] = str(e)
    except (requests.RequestException, OSError, ValueError, KeyError) as e:
        rec["error"] = f"{type(e).__name__}: {e}"
    return rec


def failed_names(rec):
    if rec["error"] and not rec["checks"]:
        return ["attempt_error"]
    return [k for k, c in rec["checks"].items() if not c["pass"]]


def cleanup_attempts(out_dir, attempts, best, keep_work):
    for rec in attempts:
        d = Path(rec["dir"])
        if not d.exists():
            continue
        if rec["attempt"] != best["attempt"] and not keep_work:
            shutil.rmtree(d, ignore_errors=True)
        elif not keep_work:
            for pat in ("*_pixeloe.png", "*_src.png", "*.bak"):
                for f in d.glob(pat):
                    f.unlink(missing_ok=True)


# ---------------------------------------------------------------- main

def parse_args(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("out_dir")
    ap.add_argument("--name", required=True, help="Output basename")
    ap.add_argument("--brief", help="The subject in plain words")
    ap.add_argument("--from-image", dest="from_image", help="Skip generation; process this image")
    ap.add_argument("--model", choices=list(MODELS), default="sdxl")
    ap.add_argument("--size", type=int, default=64, help="Target sprite long side in art pixels")
    ap.add_argument("--colors", type=int, default=24, help="Palette cap, 2-32")
    ap.add_argument("--view", choices=list(VIEW_PHRASE), default="front")
    ap.add_argument("--seed", type=int, help="First attempt's seed (later attempts add 1)")
    ap.add_argument("--retries", type=int, default=3, help="Total attempts, not extra ones")
    ap.add_argument("--timeout", type=int, help="Hard cap per generation, seconds (default 300; qwen 600)")
    ap.add_argument("--server", help="ComfyUI URL (else env COMFYUI_URL, else probe :8188 then :8000)")
    ap.add_argument("--no-defringe", action="store_true")
    ap.add_argument("--keep-work", action="store_true", help="Keep every attempt's intermediate files")
    a = ap.parse_args(argv)
    if bool(a.brief) == bool(a.from_image):
        ap.error("give exactly one of --brief or --from-image")
    if not 2 <= a.colors <= 32:
        ap.error("--colors must be 2..32")
    if not 8 <= a.size <= 256:
        ap.error("--size must be 8..256")
    if a.retries < 1:
        ap.error("--retries must be at least 1")
    if a.timeout is not None and a.timeout < 1:
        ap.error("--timeout must be positive")
    if re.search(r'[\\/:*?"<>|]', a.name) or not a.name.strip():
        ap.error("--name must be a plain file name (no path separators or reserved characters)")
    if a.from_image and not os.path.isfile(a.from_image):
        ap.error(f"--from-image not found: {a.from_image}")
    if a.model == "sdxl-pixel" and a.brief and not LORA_PATH.is_file():
        ap.error(f"--model sdxl-pixel needs {LORA_PATH}, which is not on disk (it is not downloaded automatically)")
    return a


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    spec = MODELS[args.model]
    out_dir = Path(args.out_dir).resolve()
    server, stats = None, {}
    if args.brief:
        hit = resolve_server(args.server)
        if not hit:
            print(NOT_RUNNING_MSG, file=sys.stderr)
            return 3
        server, stats = hit
    t_start = time.perf_counter()
    out_dir.mkdir(parents=True, exist_ok=True)

    prompt = build_prompt(args.brief, args.view) if args.brief else None
    # qwen gets one attempt per asset (it can run ~10 min); --from-image is deterministic, so a retry would only repeat it
    total_attempts = 1 if (args.from_image or args.model == "qwen") else args.retries
    base_seed = args.seed if args.seed is not None else random.randrange(1, 2**31 - 1 - total_attempts)
    attempts = []
    for n in range(1, total_attempts + 1):
        rec = one_attempt(args, n, base_seed + n - 1, out_dir / "_attempts" / f"attempt{n}", server,
                          prompt, spec, args.from_image)
        attempts.append(rec)
        if rec["passed"]:
            break
    passing = [r for r in attempts if r["passed"]]
    best = passing[0] if passing else min(attempts, key=lambda r: (len(failed_names(r)), r["attempt"]))
    verdict = "pass" if passing else "fail"

    outputs = {"report": str(out_dir / f"{args.name}_report.json")}
    pack_info = {"attempted": False}
    if best.get("grid") and Path(best["grid"]).exists():
        grid_copy = out_dir / f"{args.name}_grid.png"
        shutil.copy2(best["grid"], grid_copy)
        outputs["grid"] = str(grid_copy)
        preview = out_dir / f"{args.name}_preview.png"
        make_preview(grid_copy, preview)
        outputs["preview"] = str(preview)
        if verdict == "pass":
            ok, packed, log = pack(grid_copy, out_dir, args.name, args.colors)
            pack_info = {"attempted": True, "ok": ok, "log": log}
            outputs.update(packed)
            if not ok:
                verdict = "fail"
                best["error"] = f"ase_pack.py failed: {log}"
    cleanup_attempts(out_dir, attempts, best, args.keep_work)

    report = {
        "name": args.name, "brief": args.brief, "from_image": args.from_image, "prompt": prompt,
        "negative_prompt": NEGATIVE if args.brief else None,
        "model": args.model if args.brief else None,
        "licence_note": spec["licence"] if args.brief else "existing image: provenance and licence not checked by this tool",
        "server": server, "vram_free_bytes_before": vram_free(stats) if stats else None,
        "params": {"size": args.size, "colors": args.colors, "view": args.view, "retries": total_attempts,
                   "timeout": (args.timeout or spec["timeout"]) if args.brief else None,
                   "defringe": not args.no_defringe},
        "attempts": attempts, "best_attempt": best["attempt"], "defringe": best["defringe"],
        "checks": best["checks"], "pack": pack_info, "verdict": verdict, "outputs": outputs,
        "seconds_total": round(time.perf_counter() - t_start, 1),
    }
    Path(outputs["report"]).write_text(json.dumps(report, indent=2), encoding="utf-8")

    fails = failed_names(best)
    d = best["defringe"] or {}
    dtxt = (f"applied, {d['removed']} px removed" if d.get("applied") else d.get("skipped_reason", "not run"))
    print(f"sprite_make: {args.name} -> {verdict.upper()} ({'from-image' if not args.brief else args.model}, "
          f"attempt {best['attempt']} of {len(attempts)}, {report['seconds_total']}s)")
    print(f"  grid: {'x'.join(map(str, best.get('grid_size', ['?'])))}, "
          f"{best['checks'].get('colors_within_cap', {}).get('colors', '?')} colours, "
          f"{best['checks'].get('subject_fill', {}).get('fill', '?')} fill")
    print(f"  checks: {'all passed' if not fails else 'FAILED: ' + ', '.join(fails)}"
          + (f" ({best['error']})" if best.get("error") else ""))
    print(f"  defringe: {dtxt}")
    print(f"  report: {outputs['report']}")
    return 0 if verdict == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
