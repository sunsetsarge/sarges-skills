"""Local image-to-3D through ComfyUI's built-in TRELLIS.2 / Pixal3D nodes (no Meshy credits).

Takes one picture of an object or character and writes a textured GLB plus its baked maps.
Drives the stock template "3d_pixal3d_trellis2_image_to_model" that ships with ComfyUI, so the
result is the same one the Templates menu gives in the app.

  python local_i23d.py --image orc.png --out out\\orc                     # TRELLIS.2, shape 1024, 2K maps
  python local_i23d.py --image orc.png --out out\\orc --model pixal3d     # Pixal3D instead
  python local_i23d.py --image orc.png --out out\\orc --launch            # start ComfyUI headless first

Run it with ComfyUI's own Python (it needs aiohttp):  C:\\ComfyUI\\.venv\\Scripts\\python.exe
ComfyUI must be reachable at --server. The Desktop app listens on 8188. --launch starts a
headless copy on the port in --server when nothing answers there, and stops it afterwards.

The result is a ~600k-triangle model. For a game-size one run lowpoly_bake.py on model_*.glb next.
The GPU must be otherwise idle (about 2 GB in use at most): with a loaded Ollama model or another
generation on the card this runs out of memory or takes several times as long. 4 to 8 minutes on
an RTX 3080 that is otherwise free.

Needs these seven files under ComfyUI's models folder (from the Comfy-Org repos on Hugging Face
that the template links to):
  diffusion_models\\trellis_2_int8_convrot.safetensors, diffusion_models\\pixal3d_int8_convrot.safetensors,
  vae\\trellis_2_shape_vae_bf16.safetensors, vae\\trellis_2_texture_vae_bf16.safetensors,
  clip_vision\\dino_v3_L_naf_fp32.safetensors, geometry_estimation\\moge_2_vitl_normal_fp16.safetensors,
  background_removal\\birefnet.safetensors

Exit code 0 only when ComfyUI reports success AND a GLB was downloaded. report.json in --out
holds per-node seconds, peak VRAM and the file list.
"""
import argparse
import asyncio
import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

import aiohttp

TEMPLATE = "3d_pixal3d_trellis2_image_to_model"
WIDGET_TYPES = {"INT", "FLOAT", "STRING", "BOOLEAN", "COMBO", "COMFY_DYNAMICCOMBO_V3", "COLOR", "LOAD_3D"}
SKIP_TYPES = {"MarkdownNote", "Note"}
FILE_RE = re.compile(r"\.[A-Za-z0-9]{2,5}( \[(temp|output|input)\])?$")



def default_launch_cmd():
    """How the Comfy Desktop app starts its ComfyUI on a standard Windows install: its own venv
    and data under COMFYUI_BASE (default C:\\ComfyUI), the code under the user's ComfyUI-Installs,
    and the model-paths file the app generated. Override with --launch-cmd on any other layout."""
    home = Path(os.environ.get("USERPROFILE") or Path.home())
    appdata = Path(os.environ.get("APPDATA") or home / "AppData" / "Roaming")
    base = Path(os.environ.get("COMFYUI_BASE", r"C:\ComfyUI"))
    cmd = [str(base / ".venv" / "Scripts" / "python.exe"),
           str(home / "ComfyUI-Installs" / "ComfyUI" / "ComfyUI" / "main.py"),
           "--base-directory", str(base),
           "--output-directory", str(base / "output"),
           "--input-directory", str(base / "input"),
           "--user-directory", str(base / "user")]
    model_paths = sorted((appdata / "Comfy Desktop" / "instance-model-paths").glob("*.yaml"))
    if model_paths:
        cmd += ["--extra-model-paths-config", str(model_paths[0])]
    return cmd


LAUNCH_CMD = default_launch_cmd()


def _is_widget(spec):
    return isinstance(spec[0], list) or spec[0] in WIDGET_TYPES


def _opts(spec):
    return spec[1] if len(spec) > 1 and isinstance(spec[1], dict) else {}


def ui_to_api(wf, oi):
    """Workflow (UI/graph format) -> API prompt, using the server's /object_info for widget order."""
    links = {l[0]: l for l in wf["links"]}
    prompt, warnings = {}, []
    for n in wf["nodes"]:
        t = n["type"]
        if t in SKIP_TYPES:
            continue
        if n.get("mode", 0) != 0:
            warnings.append(f"node {n['id']} {t} is muted/bypassed (mode {n.get('mode')}); not handled")
        if t not in oi:
            raise SystemExit(f"ComfyUI has no node '{t}'. Update ComfyUI (needs the built-in TRELLIS.2 nodes).")
        d = oi[t]
        inputs = {}
        linked = {}
        for i in n.get("inputs", []):
            if i.get("link") is not None:
                L = links[i["link"]]
                linked[i["name"]] = [str(L[1]), L[2]]
        wv = n.get("widgets_values")
        wv = list(wv) if isinstance(wv, list) else []
        pos = 0

        def take(o):
            nonlocal pos
            if pos < len(wv):
                v = wv[pos]
                pos += 1
                return v, True
            return o.get("default"), False

        for sec in ("required", "optional"):
            for name, spec in (d["input"].get(sec) or {}).items():
                if not _is_widget(spec):
                    if name in linked:
                        inputs[name] = linked[name]
                    continue
                o = _opts(spec)
                v, had = take(o)
                if not had:
                    warnings.append(f"node {n['id']} {t}.{name}: no saved value, using default {v!r}")
                if o.get("control_after_generate"):
                    pos += 1  # the fixed/randomize companion widget
                if spec[0] == "COMFY_DYNAMICCOMBO_V3":
                    sel = next((op for op in o.get("options", []) if op.get("key") == v), None)
                    if sel is None:
                        warnings.append(f"node {n['id']} {t}.{name}: option {v!r} not found")
                    else:
                        sub = sel.get("inputs") or {}
                        for ssec in ("required", "optional"):
                            for sname, sspec in (sub.get(ssec) or {}).items():
                                inputs[f"{name}.{sname}"] = take(_opts(sspec))[0]
                if name in linked:
                    inputs[name] = linked[name]
                elif v is not None or had:
                    if spec[0] == "INT" and isinstance(v, str):
                        v = int(v)
                    inputs[name] = v
        left = len(wv) - pos
        if left > 0 and not (t == "LoadImage" and left == 1):
            warnings.append(f"node {n['id']} {t}: {left} unused widget value(s) {wv[pos:]}")
        prompt[str(n["id"])] = {"class_type": t, "inputs": inputs, "_meta": {"title": n.get("title") or t}}
    return prompt, warnings


def http_json(url, timeout=120):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.load(r)


def server_up(server):
    try:
        http_json(server + "/system_stats", timeout=5)
        return True
    except Exception:
        return False


def launch(server, cmd, log_path):
    port = urllib.parse.urlparse(server).port or 8188
    log = open(log_path, "w", encoding="utf-8", errors="replace")
    proc = subprocess.Popen(cmd + ["--port", str(port)], stdout=log, stderr=subprocess.STDOUT)
    deadline = time.time() + 600
    while time.time() < deadline:
        if proc.poll() is not None:
            raise SystemExit(f"ComfyUI exited during startup (code {proc.returncode}); see {log_path}")
        if server_up(server):
            return proc
        time.sleep(2)
    proc.terminate()
    raise SystemExit(f"ComfyUI did not answer at {server} within 10 minutes; see {log_path}")


def vram_sampler(stop, out):
    peak, base = 0, None
    while not stop.is_set():
        try:
            r = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                               capture_output=True, text=True, timeout=10)
            u = int(r.stdout.strip().splitlines()[0])
            base = u if base is None else base
            peak = max(peak, u)
        except Exception:
            pass
        stop.wait(1.0)
    out["vram_start_mib"], out["vram_peak_mib"] = base, peak


async def upload(session, server, path):
    data = aiohttp.FormData()
    data.add_field("image", open(path, "rb"), filename=Path(path).name)  # ComfyUI renames on a name clash
    async with session.post(server + "/upload/image", data=data) as r:
        body = await r.json()
        if r.status != 200:
            raise SystemExit(f"image upload failed: {body}")
        return f"{body['subfolder']}/{body['name']}" if body.get("subfolder") else body["name"]


async def run(server, prompt, report, out_dir):
    client_id = uuid.uuid4().hex
    titles = {k: f"{v['_meta']['title']} [{v['class_type']}]" for k, v in prompt.items()}
    timeline = []
    async with aiohttp.ClientSession() as s:
        async with s.ws_connect(server.replace("http", "ws", 1) + f"/ws?clientId={client_id}", max_msg_size=0) as ws:
            async with s.post(server + "/prompt", json={"prompt": prompt, "client_id": client_id}) as r:
                body = await r.json()
                if r.status != 200:
                    report["submit_error"] = body
                    print("SUBMIT ERROR:", json.dumps(body)[:1500])
                    return False
                pid = body["prompt_id"]
            t0 = time.time()
            cur, cur_t = None, t0
            async for msg in ws:
                if msg.type != aiohttp.WSMsgType.TEXT:
                    continue
                m = json.loads(msg.data)
                ty, data = m.get("type"), m.get("data", {})
                if data.get("prompt_id") not in (None, pid):
                    continue
                if ty == "executing":
                    now = time.time()
                    if cur is not None:
                        sec = round(now - cur_t, 1)
                        timeline.append({"node": cur, "title": titles.get(cur, cur), "sec": sec})
                        if sec >= 1:
                            print(f"  {sec:7.1f}s  {titles.get(cur, cur)}", flush=True)
                    cur, cur_t = data.get("node"), now
                    if cur is None:
                        break
                elif ty == "execution_error":
                    report["execution_error"] = {k: data.get(k) for k in
                                                 ("node_id", "node_type", "exception_type", "exception_message")}
                    print("EXECUTION ERROR:", data.get("node_type"), data.get("exception_type"),
                          str(data.get("exception_message"))[:800], flush=True)
                    break
                elif ty == "execution_success":
                    break
            report["total_sec"] = round(time.time() - t0, 1)
        report["timeline"] = timeline
        async with s.get(server + f"/history/{pid}") as r:
            h = (await r.json()).get(pid, {})
        report["status"] = h.get("status", {}).get("status_str")
        files = []
        for nid, o in (h.get("outputs") or {}).items():
            title = prompt.get(nid, {}).get("_meta", {}).get("title", nid)
            cls = prompt.get(nid, {}).get("class_type", "")
            for items in o.values():
                if not isinstance(items, list):
                    continue
                for it in items:
                    name = it.get("filename") if isinstance(it, dict) else it if isinstance(it, str) else None
                    if not name or "\n" in name or not FILE_RE.search(name):
                        continue  # text results (mesh info and the like), not files
                    sub = it.get("subfolder", "") if isinstance(it, dict) else ""
                    typ = it.get("type", "output") if isinstance(it, dict) else "output"
                    # 3D nodes report plain strings: "subfolder/file.glb" or "file.glb [temp]"
                    for folder in ("temp", "output", "input"):
                        if name.endswith(f" [{folder}]"):
                            name, typ = name[: -len(folder) - 3], folder
                    if "/" in name and not sub:
                        sub, name = name.rsplit("/", 1)
                    ext = name.rsplit(".", 1)[-1].lower()
                    label = title.lower().replace(" ", "_").replace(":", "")
                    local = f"{'model' if cls == 'Save3DAdvanced' else label}_{nid}.{ext}"
                    if any(f["file"] == local for f in files):
                        continue
                    q = urllib.parse.urlencode({"filename": name, "subfolder": sub, "type": typ})
                    async with s.get(server + "/view?" + q) as vr:
                        if vr.status == 200:
                            (out_dir / local).write_bytes(await vr.read())
                            files.append({"file": local, "from": f"{typ}:{sub}/{name}", "node": f"{title} [{cls}]"})
                        else:
                            print(f"WARN: could not fetch {typ}:{sub}/{name} (HTTP {vr.status})", flush=True)
        report["files"] = files
    return report.get("status") == "success" and "execution_error" not in report


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--image", required=True, help="picture of the subject (plain background helps)")
    ap.add_argument("--out", required=True, help="folder for the GLB, baked maps and report.json")
    ap.add_argument("--model", choices=["trellis2", "pixal3d"], default="trellis2")
    ap.add_argument("--tex", type=int, default=2048, help="texture size in px (template ships 4096)")
    ap.add_argument("--upsample", type=int, default=1024,
                    help="shape resolution; the template's 1536 runs out of memory on a 10 GB card")
    ap.add_argument("--faces", type=int,
                    help="triangle count (template default 700000). Do not go low here: the mesh is a "
                         "thin double wall and tears. Reduce with lowpoly_bake.py instead")
    ap.add_argument("--no-bg-removal", action="store_true", help="image already has the alpha/mask you want")
    ap.add_argument("--seed", type=int, help="same seed for all four samplers (template uses fixed seeds)")
    ap.add_argument("--server", default="http://127.0.0.1:8188")
    ap.add_argument("--launch", action="store_true", help="start ComfyUI headless if --server does not answer")
    ap.add_argument("--launch-cmd", help="JSON list overriding the ComfyUI start command (without --port)")
    ap.add_argument("--template", help="workflow JSON file; default: ask the server for the stock template")
    ap.add_argument("--dry", action="store_true", help="print the API prompt and stop")
    a = ap.parse_args()

    out_dir = Path(a.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    proc = None
    if not server_up(a.server):
        if not a.launch:
            raise SystemExit(f"Nothing answers at {a.server}. Open Comfy Desktop, or pass --launch.")
        cmd = json.loads(a.launch_cmd) if a.launch_cmd else LAUNCH_CMD
        print("starting ComfyUI headless ...", flush=True)
        proc = launch(a.server, cmd, out_dir / "comfyui_server.log")
    try:
        wf = json.load(open(a.template, encoding="utf-8")) if a.template else \
            http_json(f"{a.server}/templates/{TEMPLATE}.json")
        prompt, warnings = ui_to_api(wf, http_json(a.server + "/object_info"))
        for w in warnings:
            print("WARN:", w)

        def one(cls=None, title=None):
            hits = [k for k, v in prompt.items()
                    if (cls is None or v["class_type"] == cls) and (title is None or v["_meta"]["title"] == title)]
            if len(hits) != 1:
                raise SystemExit(f"template changed: expected one node for {cls or title}, found {len(hits)}")
            return prompt[hits[0]]["inputs"]

        one(title="Boolean (Switch to Trellis2)")["value"] = a.model == "trellis2"
        one(cls="Save3DAdvanced")["filename_prefix"] = f"3d/local_i23d/{out_dir.name}"
        if a.tex:
            one(title="Texture Resolution")["value"] = a.tex
        if a.upsample:
            one(cls="Trellis2UpsampleStage")["target_resolution"] = a.upsample
        if a.faces:
            one(cls="DecimateMesh")["target_face_count"] = a.faces
        if a.no_bg_removal:
            one(title="Switch: Remove background")["switch"] = False
        if a.seed is not None:
            for v in prompt.values():
                if v["class_type"] == "KSampler":
                    v["inputs"]["seed"] = a.seed
        if a.dry:
            print(json.dumps(prompt, indent=1))
            return 0

        report = {"args": vars(a), "warnings": warnings}
        stop = threading.Event()
        th = threading.Thread(target=vram_sampler, args=(stop, report), daemon=True)

        async def go():
            async with aiohttp.ClientSession() as s:
                one(cls="LoadImage")["image"] = await upload(s, a.server, a.image)
            th.start()
            return await run(a.server, prompt, report, out_dir)

        ok = asyncio.run(go())
        stop.set()
        if th.is_alive():
            th.join(timeout=5)
        glbs = [f for f in report.get("files", []) if f["file"].startswith("model_")]
        report["ok"] = bool(ok and glbs)
        (out_dir / "report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
        print(json.dumps({k: report.get(k) for k in ("ok", "status", "total_sec", "vram_start_mib", "vram_peak_mib")}))
        for f in report.get("files", []):
            print("  ", f["file"])
        return 0 if report["ok"] else 1
    finally:
        if proc is not None:
            proc.terminate()


if __name__ == "__main__":
    sys.exit(main())
