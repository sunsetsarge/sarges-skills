"""Direct ComfyUI HTTP API client for a basic checkpoint txt2img graph
(Lane B: dreamshaperPixelart_v10, or any other plain SD checkpoint that isn't
covered by one of comfyui-studio's GGUF templates).

Prefer submitting through the comfyui MCP tools (enqueue_workflow /
get_history / view_image) when they're registered in the session -- that's
comfyui-studio's normal flow and it owns recovery/VRAM management. Use this
script as a fallback when the MCP isn't available: it was needed during this
skill's own Phase 0 build (the MCP wasn't registered in that session) and
talks to the same server at 127.0.0.1:8000 that comfyui-studio uses.
"""
import argparse
import time
import uuid
from pathlib import Path

import requests

SERVER = "http://127.0.0.1:8000"


def build_workflow(checkpoint: str, prompt: str, negative: str, width: int, height: int,
                    steps: int, cfg: float, sampler: str, scheduler: str, seed: int) -> dict:
    return {
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "seed": seed, "steps": steps, "cfg": cfg,
                "sampler_name": sampler, "scheduler": scheduler, "denoise": 1.0,
                "model": ["4", 0], "positive": ["6", 0], "negative": ["7", 0],
                "latent_image": ["5", 0],
            },
        },
        "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": checkpoint}},
        "5": {"class_type": "EmptyLatentImage",
              "inputs": {"width": width, "height": height, "batch_size": 1}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["4", 1]}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": ["4", 1]}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
        "9": {"class_type": "SaveImage",
              "inputs": {"images": ["8", 0], "filename_prefix": "pixelart_studio"}},
    }


def submit_and_wait(workflow: dict, timeout: int = 900) -> dict:
    client_id = str(uuid.uuid4())
    resp = requests.post(f"{SERVER}/prompt", json={"prompt": workflow, "client_id": client_id})
    resp.raise_for_status()
    prompt_id = resp.json()["prompt_id"]
    print(f"submitted prompt_id={prompt_id}")

    start = time.time()
    while time.time() - start < timeout:
        hist = requests.get(f"{SERVER}/history/{prompt_id}").json()
        if prompt_id in hist:
            entry = hist[prompt_id]
            if entry.get("status", {}).get("completed"):
                return entry
            status_str = entry.get("status", {}).get("status_str")
            if status_str == "error":
                raise RuntimeError(f"ComfyUI job failed: {entry['status']}")
        time.sleep(2)
    raise TimeoutError(f"prompt {prompt_id} did not complete within {timeout}s")


def download_output(entry: dict, out_path: Path) -> Path:
    outputs = entry["outputs"]
    for node_id, node_out in outputs.items():
        for img in node_out.get("images", []):
            params = {"filename": img["filename"], "subfolder": img.get("subfolder", ""),
                      "type": img.get("type", "output")}
            r = requests.get(f"{SERVER}/view", params=params)
            r.raise_for_status()
            out_path.write_bytes(r.content)
            return out_path
    raise RuntimeError("no image found in job outputs")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--negative", default="blurry, anti-aliased, smooth gradient, "
                                           "photorealistic, 3d render, text, watermark, "
                                           "soft shading, jpeg artifacts")
    ap.add_argument("--width", type=int, default=512)
    ap.add_argument("--height", type=int, default=512)
    ap.add_argument("--steps", type=int, default=25)
    ap.add_argument("--cfg", type=float, default=7.0)
    ap.add_argument("--sampler", default="dpmpp_2m")
    ap.add_argument("--scheduler", default="karras")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("-o", "--output", required=True)
    args = ap.parse_args()

    wf = build_workflow(args.checkpoint, args.prompt, args.negative, args.width, args.height,
                         args.steps, args.cfg, args.sampler, args.scheduler, args.seed)
    entry = submit_and_wait(wf)
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    download_output(entry, out_path)
    print(f"saved -> {out_path}")


if __name__ == "__main__":
    main()
