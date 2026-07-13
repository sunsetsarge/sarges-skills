"""Run a local PNG through Qwen-Image-Edit-2511 with a plain-English edit
instruction, via direct ComfyUI HTTP API (reuses comfyui-studio's
studio-edit-qwen2511.json template verbatim). Used to test pose/frame edits
for walk/idle cycles -- character-consistency lever per PLAN.md Phase 2
("same-seed + IPAdapter and/or Qwen-Edit-2511 restyle/pose edits").

Note: comfyui-studio's SKILL.md warns the first cold run of this template is
~22 min (13GB GGUF offload); subsequent runs in the same ComfyUI session are
much faster once the model is warm. Don't cancel "Model Initializing".
"""
import argparse
import json
from pathlib import Path

import requests

from comfy_submit import submit_and_wait, download_output, SERVER

TEMPLATE = Path(r"C:\Claude\sarges-skills\skills\comfyui-studio\assets\workflows\studio-edit-qwen2511.json")


def upload_image(path: Path) -> str:
    with open(path, "rb") as f:
        r = requests.post(f"{SERVER}/upload/image", files={"image": (path.name, f, "image/png")})
    r.raise_for_status()
    return r.json()["name"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("--instruction", required=True)
    ap.add_argument("--width", type=int, default=512)
    ap.add_argument("--height", type=int, default=512)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("-o", "--output", required=True)
    args = ap.parse_args()

    input_path = Path(args.input).resolve()
    uploaded_name = upload_image(input_path)
    print(f"uploaded -> {uploaded_name}")

    wf = json.loads(TEMPLATE.read_text())
    wf["5"]["inputs"]["image"] = uploaded_name
    wf["6"]["inputs"]["prompt"] = args.instruction
    wf["8"]["inputs"]["width"] = args.width
    wf["8"]["inputs"]["height"] = args.height
    wf["9"]["inputs"]["seed"] = args.seed

    entry = submit_and_wait(wf, timeout=1800)
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    download_output(entry, out_path)
    print(f"saved -> {out_path}")


if __name__ == "__main__":
    main()
