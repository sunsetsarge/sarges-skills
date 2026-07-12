"""Submit a template workflow JSON (ComfyUI API format, node-id-keyed) with a
patched prompt/seed, via direct HTTP. Used for Lane A (Qwen) -- reuses
comfyui-studio's studio-text-in-image-qwen.json verbatim, or this skill's own
assets/workflows/lane-a-qwen.json. See comfy_submit.py's docstring for when
to prefer the comfyui MCP over this fallback.
"""
import argparse
import json
from pathlib import Path

from comfy_submit import submit_and_wait, download_output


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("template", help="Path to a ComfyUI API-format workflow JSON")
    ap.add_argument("--prompt-node", required=True, help="Node id whose 'text' input to set")
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--seed-node", help="Node id whose 'seed' input to set")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("-o", "--output", required=True)
    args = ap.parse_args()

    wf = json.loads(Path(args.template).read_text())
    wf[args.prompt_node]["inputs"]["text"] = args.prompt
    if args.seed_node:
        wf[args.seed_node]["inputs"]["seed"] = args.seed

    entry = submit_and_wait(wf, timeout=900)
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    download_output(entry, out_path)
    print(f"saved -> {out_path}")


if __name__ == "__main__":
    main()
