"""Run a local PNG through the RMBG background-removal workflow
(assets/workflows/rmbg-postprocess.json) via direct ComfyUI HTTP API, and
save the alpha-baked result. Use this before pixelize.py when the source has
a busy/scenic background that unfake's own --alpha flood-fill won't clean up
(see references/pixel-prompting.md) -- e.g. most Lane A/B ComfyUI output,
which tends to render a full scene even when the prompt asks for a plain
background.
"""
import argparse
import json
from pathlib import Path

import requests

from comfy_submit import submit_and_wait, download_output, SERVER

WORKFLOW = Path(__file__).resolve().parent.parent / "assets" / "workflows" / "rmbg-postprocess.json"


def upload_image(path: Path) -> str:
    with open(path, "rb") as f:
        r = requests.post(f"{SERVER}/upload/image", files={"image": (path.name, f, "image/png")})
    r.raise_for_status()
    return r.json()["name"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument("--model", default="INSPYRENET", choices=["RMBG-2.0", "INSPYRENET", "BEN", "BEN2"])
    args = ap.parse_args()

    input_path = Path(args.input).resolve()
    uploaded_name = upload_image(input_path)
    print(f"uploaded -> {uploaded_name}")

    wf = json.loads(WORKFLOW.read_text())
    wf["1"]["inputs"]["image"] = uploaded_name
    wf["2"]["inputs"]["model"] = args.model

    entry = submit_and_wait(wf)
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    download_output(entry, out_path)
    print(f"saved -> {out_path}")


if __name__ == "__main__":
    main()
