---
name: vintage-ad-generator
argument-hint: "<town> <business/subject> [--headline TEXT]"
description: Generate ORIGINAL vintage/period newspaper-ad artwork locally (ComfyUI, RTX 3080) for the Saspan Salt / Local Lore Apparel line — an engraving-style illustration composited with real period type into a finished 1900s–1940s ad. Use whenever the user wants to CREATE a new or original vintage/period advertising design, a heritage or nostalgia tee, a Local Lore town ad, a "fake old newspaper ad", or complains that AI-generated vintage art "looks too AI / has weird proportions / doesn't match the theme." This is for GENERATING new designs — NOT for restoring real historical ads (that is the digitalnc-harvest pipeline), and it is distinct from the generic ComfyUI skill. Encodes the medium-forcing engraving recipe, the --fp16-vae black-render trap, commercial-safe model choices, reference-anchoring, and the make_tee_mock.py type-composite step.
---

# Vintage Ad Generator (local, ComfyUI)

Generate ORIGINAL period-newspaper-ad artwork on the RTX 3080: an engraving-style **illustration** from a local diffusion model, composited with **real hand-set type** into a finished 1900s–1940s advertisement for the Saspan Salt / Local Lore Apparel line.

**The one principle that makes it work:** generate the *picture* with AI, set the *words* with fonts. Diffusion models garble text and drift toward a smooth, photographic look; a real ad was a printer's engraved "cut" plus hand-set type anyway — so force the engraving *medium* for the illustration and never let the model spell.

> Scope: for **new / original** designs (novelty, town-pride, a business with no surviving ad). Restoring *real* public-domain ads is the separate [[digitalnc-harvest]] pipeline — those already look great and need no generation. Also distinct from a generic ComfyUI skill; it encodes the specific recipe + traps below.

## Operational config
Paths, the Python interpreter, and model defaults live in **`config.json`** (next to this file) — the single source of truth for *where things are*. Read it to build commands; edit *it* to relocate, not this doc.

## Why AI vintage ads usually "look too AI" (and the fix)
The complaint — "too AI, weird proportions, doesn't match the theme" — is a **medium mismatch**. Models default to smooth, shaded, semi-photographic rendering; a 1900s–40s ad is a flat **line engraving** (cross-hatching + stipple, pure black ink, no gradients). Force the medium and the "AI" tell disappears — and the stylization also *hides* the anatomy/proportion errors that wreck photoreal generation.

## Step 0 — ComfyUI up
Launch from `comfyui_path`: `.\.venv\Scripts\python.exe main.py --highvram --fast --fp16-vae`. API at `comfyui_url`. Generation runs **headless via the ComfyUI MCP** → nothing appears on the GUI canvas; PNGs land in `output_dir` (view via the GUI **Queue** history or just open the file).

> ⛔ **`--fp16-vae` black-render trap:** it NaNs the stock SDXL **base** VAE → a solid-black ~0 KB PNG while the job still reports `success`. If a render is black, this is why. Use SD1.5 or Qwen (below), an SDXL checkpoint with a baked fp16-safe VAE, or drop the flag.

## Model selection (commercial-safe — this is for a business)
| Use | Model | License |
|---|---|---|
| **Default / style scratchpad** | `dreamshaper_8` (SD1.5) | 🟢 OpenRAIL — VAE-safe, artistic, fast |
| Higher-res / more control | SDXL (safe-VAE checkpoints) | 🟢 OpenRAIL++ |
| **Reliable subjects + legible in-image text** | Qwen-Image / Qwen-Image-Edit (GGUF) | 🟢 Apache |
| ⛔ Avoid for products | FLUX dev, FLUX.2 Klein **9B**, Kontext dev, SUPIR, CodeFormer | 🔴 non-commercial |

## Step 1 — generate the engraving illustration
Keep `[SUBJECT]` a **single clear subject** — SD1.5 silently drops extra elements.

**POSITIVE:** `1900s-1940s newspaper advertisement engraving, [SUBJECT], black ink line art on white paper, dense cross-hatching and stipple shading, high contrast black and white, antique letterpress advertising cut, engraved linework, no gradients` (add `, no people` for a product-only cut)

**NEGATIVE:** `photograph, photorealistic, color, colored, gray gradient, soft shading, 3d render, cgi, digital painting, blurry, modern, halftone dots, smooth, text, letters, watermark, person, people, human, figure, face` (add `, car, boat` as needed)

Settings (see `config.json` `defaults`): SD1.5, **512×768 or 640×768**, 30–32 steps, CFG 7, `dpmpp_2m` / `karras`, **batch 4**.

> ⚠️ **Cherry-pick — SD1.5 lands a clean, on-brief cut roughly 1 in 2.** It renders the medium beautifully but **drops elements** (ask for "store + gas pumps" → get the store, no pumps) and **cannot spell** (produces "OUSTER", gibberish banners). So: batch 4, pick the best, keep words OUT of the image. For reliable multi-element scenes or legible in-image text, escalate to **Qwen-Image** or a **ControlNet** anchor (see Reference-anchoring).

## Step 2 — composite into a finished ad (illustration + real type)
Run the bundled script — it drops the cut's white background to ink-on-cream, draws a period double-border + rules, and sets the type in Windows serif fonts (Rockwell → Bookman → Georgia-Bold fallback):

```
<comfyui_python> scripts/make_tee_mock.py \
  --cut <best_cut.png> --headline "GALLOWAY'S" \
  --services "GENERAL MERCHANDISE  ·  GAS" --town "SHALLOTTE, N. C." \
  --kicker "AROUND THE CLOCK" --tagline "GAS · OILS · LUNCHES — OPEN ALL HOURS" \
  --out <finished.png>
```
Use **authentic borrowed copy** (next section). The script prints `final y of H`; if content overflows the border, bump `--height`.

## Reference-anchoring (authenticity, zero-IP)
- **Copy + business names + layout** → the DigitalNC corpus (`corpus_ad_crops`). Real 1940s Brunswick ads are **type-only** — no illustrations to trace (the illustrated cuts are the 1900s–10s *Wilmington* ads), so mine them for *words*, not pictures. Real documented names: **Galloway's General Store, Pemberton's Esso, Bryant Bros, Lindsey Piggott, Geneva Evans "Gas Stop"**, Shallotte Furniture Co.
- **A pictorial scene (store WITH pumps, etc.)** → a **public-domain Library of Congress** photo (FSA 1940s rural stores; Carol Highsmith CC0) → make a canny/line map with Python (the in-Comfy `controlnet_aux` preprocessor is currently broken) → ControlNet → engraving. This is how you get elements SD1.5 won't reliably invent.

## IP / licensing (Blaine's guardrail)
- ⚠️ Brand names can be **live trademarks** (e.g. "Red & White" grocery). Prefer a **documented real** local business name — safer *and* more authentic. No real logos, no post-1928 scans in products.
- Only sell art made with the 🟢 models above.

## Gotchas
| Symptom | Cause | Fix |
|---|---|---|
| Solid black PNG, ~0 KB, reports "success" | `--fp16-vae` + SDXL base VAE NaN | SD1.5 / Qwen, safe-VAE model, or drop the flag |
| Looks too smooth / "AI" | prompt didn't force the medium | add engraving + cross-hatch + stipple, and anti-photo negatives |
| Garbled words baked into the image | diffusion model can't spell | set text as type in Step 2; negative-prompt `text, letters` |
| Asked-for element missing | SD1.5 weak prompt adherence | batch 4 + cherry-pick, or Qwen / ControlNet |
| "Nothing in ComfyUI" | headless API run, empty canvas | outputs are files in `output_dir` / GUI **Queue** |

## Cross-references
- Full recipe + session findings: Confluence **p.78839810** (child of *Recreating GPT-4o Image Generation Locally in ComfyUI*, p.69763074). Local-model licensing: p.78577665.
- Related skills: [[digitalnc-harvest]] (real historical-ad sourcing), [[chatgpt-desktop]] (cloud DALL·E fallback for a quick comp).
