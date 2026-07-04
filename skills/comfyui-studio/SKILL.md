---
name: comfyui-studio
description: Produce ChatGPT-quality images locally with ComfyUI — high-adherence text-to-image, legible in-image text (posters, logos, labels), photorealistic scenes, and conversational editing/inpainting ("make it night", "add a hat", "remove the sign"). Use whenever the user asks to make/generate an image, picture, poster, logo, label, or mockup with ComfyUI or without naming a tool; wants high quality / prompt adherence / correct text in an image; or wants to edit, iterate on, or upscale a generated image. Routes each job to the best installed model (Z-Image, Qwen-Image, Qwen-Edit, FLUX, SDXL) with smoke-tested workflow templates and an LLM prompt-expansion step. NOT for vintage newspaper-ad designs (vintage-ad-generator), photo restoration or CivitAI plumbing (skill-comfyui), or video (WAN/LTX packs).
---

# ComfyUI Studio — ChatGPT-level image generation, locally

**The honest one-liner: no single open model wins everything. Qwen renders text best, Z-Image leads
photorealism and overall quality-per-VRAM, Qwen-Edit-2511 owns conversational editing, SDXL has the
deepest LoRA/ControlNet ecosystem — pick per task, and rewrite the user's prompt before generating.**

This skill owns: choosing the model, the prompt expansion, and the smoke-tested generation/edit
templates. It does NOT own submission plumbing, photo restoration, or CivitAI downloads — that is
`skill-comfyui`. Original vintage-ad artwork is `vintage-ad-generator`.

## The 30-second decision table

Hardware context: RTX 3080, **10 GB VRAM** — everything below is verified to run on it (big GGUFs
partially offload; slower but correct). Server: `http://127.0.0.1:8000` via the comfyui MCP tools.

| You need | Model (exact installed files) | Graph + settings | License |
|---|---|---|---|
| **Default: quality txt2img, photoreal, complex scenes** | `RedZimage_1.5_AIO_bf16.safetensors` (Z-Image finetune, all-in-one) | `CheckpointLoaderSimple`; **30 steps, CFG 4.0, euler/simple, 1024×1024**; short negative OK. Template: `studio-txt2img-zimage.json` | Apache-2.0 (Z-Image) |
| **Draft/iterate cheaply (same model)** | same | same graph, **10 steps, CFG 1.0** (negatives ignored at CFG 1) | Apache-2.0 |
| **In-image text: posters, labels, signs** | `qwen-image-Q4_K_M.gguf` + `Qwen2.5-VL-7B-Instruct-UD-Q4_K_XL.gguf` (CLIPLoaderGGUF, type `qwen_image`) + `qwen_image_vae.safetensors` | `UnetLoaderGGUF`; with Lightning LoRA: **8 steps, CFG 1.0, euler/simple**; without: 20 steps CFG 4.0 + `ModelSamplingAuraFlow` shift 3.1; **1328×1328** native. Template: `studio-text-in-image-qwen.json` | Apache-2.0 |
| **Edit / "make it night" / inpaint** | `qwen-image-edit-2511-Q4_K_M.gguf` + same Qwen encoder/VAE | `TextEncodeQwenImageEditPlus` conditioning; Lightning: **4 steps CFG 1.0**; else 20 steps CFG 4.0, denoise 1.0. Template: `studio-edit-qwen2511.json` | Apache-2.0 |
| **Fast throwaway drafts** | `flux-2-klein-9b-Q4_K_M.gguf` + `qwen_3_8b_fp4mixed.safetensors` (`CLIPLoader` type **`flux2`**) + `flux2-vae.safetensors` | **4 steps, CFG 1.0, euler/simple, 1024×1024** (~2 min incl. load). Template: `studio-draft-klein.json` | ⛔ **NON-COMMERCIAL** (klein 9B) — never in sold products |
| **Niche style / pose control / character LoRA** | `dreamshaperXL_v21TurboDPMSDE.safetensors` or `juggernautXL_ragnarokBy.safetensors` + `controlnet-union-sdxl-promax.safetensors` | XL Turbo: 8 steps CFG 2–3 dpmpp_sde; Juggernaut: 25–30 steps CFG 4–6. 80 LoRAs installed | OpenRAIL++ |
| **Finish / 2K upscale** | `4x-UltraSharp.pth` | model upscale ×4 then scale ×0.5 → clean 2×. Template: `studio-upscale-finish.json` | — |

License guardrail (Blaine sells products): **Apache models only for anything commercial** — Qwen
family and Z-Image. FLUX.1 dev, FLUX.2 klein **9B**, and Kontext dev are non-commercial: drafts and
personal use only.

## The workflow (every request)

1. **Expand the prompt first.** Read `references/prompt-engine.md` and rewrite the user's ask into
   3–8 structured natural-language sentences (subject+counts, layout, lighting, style, camera, mood,
   quoted in-image text). This step is most of the quality gap — never skip it.
2. **Pick the row** from the table above. In-image text → Qwen. Otherwise Z-Image default.
3. **Load the template** from `assets/workflows/`, swap the prompt (and seed), enqueue via the
   comfyui MCP (`enqueue_workflow`), and **verify via `get_history`** — never trust the submit
   return alone (skill-comfyui lesson CUI-LL-001).
4. **Inspect the result yourself** (`view_image` on the completion asset) and apply the quality
   checklist below.
5. **Iterate as an edit loop, not a slot machine** (next section).

## The edit loop (the "keep tweaking in chat" behavior)

- **Look at the output** (`view_image`). Decide: *edit* (composition right, one thing wrong),
  *reprompt* (model ignored/misbound elements), or *regenerate* (fundamentally off — new seed).
- **Edit path:** `stage_output_as_input` on the chosen output → its filename goes into the
  `LoadImage` node of `studio-edit-qwen2511.json` → one plain-English instruction per pass
  ("Make it night; the market is lit by string lights"). Chain passes: stage the new output, edit again.
- **Seeds:** hold the seed fixed to iterate on one composition (fixed 42 in all templates);
  randomize (or bump) to explore. `disable_random_seed` matters when enqueuing via MCP.
- **Upscale last**, after content is final: `studio-upscale-finish.json`.

## Quality checklist (definition of done, per image)

At 1024px+ native, before calling an image done:
- [ ] Every requested element present, counts correct, attributes bound to the right object
- [ ] Requested text legible and spelled exactly as quoted
- [ ] No melted anatomy/hands, no object fusion, believable light direction
- [ ] A one-step edit path exists (the output is staged/stageable for `studio-edit-qwen2511.json`)

If a generation misses, **name the lever — don't just reroll:**

| Failure | Lever |
|---|---|
| Ignored/miscounted elements, attribute swaps | Rewrite/expand the prompt (bind attributes per subject); on non-lightning graphs raise CFG toward 4–5; if still failing, switch Z-Image → Qwen-Image (stronger adherence on dense scenes) |
| Garbled in-image text | Must be Qwen-Image; string in quotes, shorter; CFG 4 (non-lightning); reroll only after those |
| Melted anatomy / fused objects | Different seed helps less than: fewer subjects per prompt, or SDXL+ControlNet pose anchor for precise poses |
| Composition right, one element wrong | Don't regenerate — edit pass with Qwen-Edit-2511 |
| Washed out / flat | It's the finish: model-upscale pass, or on Z-Image add "high contrast, deep shadows" — do NOT chain a second full-denoise generation pass (hallucination risk, skill-comfyui CUI-LL-007) |
| Solid black ~0 KB PNG, job "succeeded" | VAE/dtype trap: `--fp16-vae` + SDXL base VAE, or Z-Image under sage-attention. Use the templates' stock VAEs; launch flags per bundled `comfyui-launch-flags` skill |
| OOM | `clear_vram` between model families (one family loaded at a time on 10 GB); retry once; then drop to the klein draft or SDXL row |
| MCP says "fetch failed" / server dead | ComfyUI Desktop crashes under system-RAM pressure from repeated GGUF family switches — don't churn families. Recovery: kill ComfyUI.exe, wait ~10 s, relaunch from `C:\Users\blain\AppData\Local\Programs\@comfyorgcomfyui-electron\`; verify `/system_stats` answers on **8000** (a too-fast relaunch binds 8188 and the MCP is pinned to 8000). Fallback that always works: `C:\ComfyUI\.venv\Scripts\python.exe C:\Users\blain\ComfyUI-Installs\ComfyUI\ComfyUI\main.py --port 8000 --base-directory C:/ComfyUI` |
| Every safetensors load errors `'ModelMMAP' object has no attribute 'get_file_handle'` | `comfy-aimdo` version mismatch (0.3.0 vs required 0.4.10) — force-reinstall it into `C:\ComfyUI\.venv` and restart (hit + fixed 2026-07-04) |

## Templates (assets/workflows/)

| File | Use when | Verified |
|---|---|---|
| `studio-txt2img-zimage.json` | default generation | ✅ 2026-07-04: quality 88 s, draft 24 s |
| `studio-text-in-image-qwen.json` | any in-image text | ✅ 2026-07-04: 62 s with Lightning 8-step |
| `studio-edit-qwen2511.json` | edits, inpaint-style changes, consistency via reference image | ✅ 2026-07-04: **first cold run ~22 min** (13 GB GGUF offload); warm cache is fast — don't cancel "Model Initializing" |
| `studio-draft-klein.json` | fast drafts (non-commercial!) | ✅ 2026-07-04: 129 s cold |
| `studio-upscale-finish.json` | final 2× clean upscale | ✅ 2026-07-04: 6 s |

Each template documents its model slots via `_meta.title`; swap models without rewiring by changing
only the loader filenames. The saved prompts are the actual smoke-test prompts — they double as
worked examples of the expansion pattern.

## Rules from failures (smoke-test gotchas — read before debugging)

See `references/SMOKE_TEST_REPORT.md` for the full list. Highlights are folded into the failure
table above; anything new you hit goes THERE, one line each, so the next session doesn't repeat it.

## VRAM notes (RTX 3080, 10 GB)

- One model family in VRAM at a time; `clear_vram` when switching. The 13 GB Qwen Q4 GGUFs run via
  partial offload — expect minutes, not seconds, without the Lightning LoRAs.
- Lightning LoRAs (`Qwen-Image-Lightning-8steps`, `Qwen-Image-Edit-2511-Lightning-4steps`) are the
  single biggest speed lever on this card.
- If a future model doesn't fit: prefer GGUF Q4_K_M quants (this install's proven pattern) over FP8
  for <12 GB cards.

## SOTA snapshot — 2026-07-04 (WILL ROT; refresh before trusting in a new quarter)

Z-Image Turbo (Apache) topped the Artificial Analysis open-weights arena; Qwen-Image-2512 led
open-source in-image text; Qwen-Image-Edit-2511 led open editing; FLUX.2 klein 4B (not the installed
9B) was the Apache FLUX option; SDXL/SD3.5 legacy-but-deepest ecosystem. Full recon:
`references/RECON_2026-07-04.md`.

### How to refresh this skill
1. `list_local_models` + `get_node_info` on the GGUF loaders → what's ACTUALLY installed now
   (trust that over every table in this file).
2. `comfyui:list_skills` / `list_packs` → new bundled families; web-check current model cards
   (versions, licenses, VRAM).
3. Update the decision table + RECON file, re-run each template once (validate → enqueue → confirm
   output), update SMOKE_TEST_REPORT.md, bump this snapshot date.

## Handoffs

- Submission plumbing details, photo **restoration** (Flux Kontext recipes), CivitAI download auth → `skill-comfyui`
- Original vintage newspaper-ad designs (engraving recipe + type compositing) → `vintage-ad-generator`
- Per-family deep dives, launch flags, troubleshooting → bundled comfyui-mcp skills
  (`read_skill`: `qwen-txt2img`, `qwen-image-edit`, `z-image-txt2img`, `flux-txt2img`,
  `comfyui-launch-flags`, `troubleshooting`) — but their "installed models" tables describe a
  different machine; trust `list_local_models` here.
