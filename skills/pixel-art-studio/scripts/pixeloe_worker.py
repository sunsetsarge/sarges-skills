"""Runs INSIDE venv-pixeloe (torch-cpu + pixeloe + torchvision) -- not meant to
be imported by other interpreters. pixelize.py invokes this as a subprocess.

Outline-aware contrast-downscale of a hi-res AI-generated image down to
roughly the target pixel-grid resolution. do_quant is always False here --
color quantization and grid-snap are unfake's job downstream (see
pixelize.py). Kept as a subprocess-callable script rather than an importable
module because pixeloe's PyPI package (v0.1.4) has broken metadata -- see
references/qc.md "Known upstream issues" for the torchvision/tqdm deps it
doesn't declare and its dead CLI entry point.
"""
import argparse
import sys

import torch
from torchvision.transforms.functional import to_tensor, to_pil_image
from PIL import Image

from pixeloe.torch.pixelize import pixelize


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--target-size", type=int, default=64,
                     help="Target pixel-grid resolution on the short edge, in art pixels")
    ap.add_argument("--thickness", type=int, default=3,
                     help="PixelOE outline expansion thickness")
    ap.add_argument("--mode", default="contrast",
                     choices=["contrast", "k_centroid", "lanczos", "nearest"])
    args = ap.parse_args()

    src = Image.open(args.input)
    alpha = src.getchannel("A") if src.mode in ("RGBA", "LA") else None
    img = src.convert("RGB")
    w, h = img.size
    pixel_size = max(1, min(w, h) // args.target_size)

    img_t = to_tensor(img).unsqueeze(0)  # [1,3,H,W], range [0,1]

    with torch.no_grad():
        out_t = pixelize(
            img_t,
            pixel_size=pixel_size,
            thickness=args.thickness,
            mode=args.mode,
            do_color_match=True,
            do_quant=False,
            no_post_upscale=True,
        )

    out_img = to_pil_image(out_t.squeeze(0).clamp(0, 1))
    if alpha is not None:
        # pixelize() only operates on RGB -- downscale the source alpha
        # separately (box filter: averages each block, matching pixeloe's own
        # block-downscale granularity) and reattach so transparency from an
        # upstream RMBG pass survives the pixeloe step instead of being
        # silently dropped by the RGB conversion above.
        alpha_small = alpha.resize(out_img.size, Image.BOX)
        out_img.putalpha(alpha_small)
    out_img.save(args.output)
    print(f"pixeloe_worker: {args.input} ({img.size}) -> {args.output} "
          f"({out_img.size}), pixel_size={pixel_size}, alpha_preserved={alpha is not None}",
          file=sys.stderr)


if __name__ == "__main__":
    main()
