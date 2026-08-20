# ComfyUI Photo Restoration — Flux Kontext Operating Instructions

**Workflow:** PixelaiLabs Flux Kontext Dev Basic (GGUF)
**Model:** `flux1-kontext-dev-Q4_K_M.gguf`

---

## Core Rules (Apply to Every Restoration Session)

1. **Denoise stays at 1.0** — always. ReferenceLatent handles image anchoring. Changing denoise does not limit what Flux changes; only the mask does (CUI-LL-006).
2. **One generation pass only** — chaining Flux passes causes hallucination. Fabric texture, skin, and fine detail get invented on the second pass at guidance >=1.6 (CUI-LL-007).
3. **Upscale separately** — after the single Flux pass, run 4x-UltraSharp + ImageSharpen (sigma 0.3, alpha 0.25). Zero hallucination risk (CUI-LL-010).
4. **Colorization is a single pass** — do not chain colorization onto a restored output via a second Flux generation. Include colorize instruction in the original prompt (CUI-LL-008).

---

## Node Chain

```
UnetLoaderGGUF + DualCLIPLoaderGGUF + VAELoader
  → LoadImage → ImageStitch → FluxKontextImageScale
  → VAEEncode → CLIPTextEncode → ConditioningZeroOut
  → ReferenceLatent → FluxGuidance → KSampler
  → VAEDecode → ImageSharpen → [optional: ReActorFaceSwap]
  → SaveImage + PreviewImage
```

---

## Step 1 — Copy the Source Image

**CRITICAL:** Do NOT use `comfy_upload_image` (APP-LL-009). Copy directly:

```powershell
Copy-Item "F:\path\to\source_photo.jpg" "C:\ComfyUI\input\source_photo.jpg" -Force
Test-Path "C:\ComfyUI\input\source_photo.jpg"
```

---

## Step 2 — Write the Prompt

### Template

```
Restore this [era] [photo type] photograph. Remove all scratches, stains,
tears, and damage marks. Enhance contrast and recover full detail for all
subjects. [Specific damage instructions]. [If colorizing: "Add natural,
realistic period-appropriate colors: warm skin tones, [era] clothing colors,
natural hair colors, neutral background."] Preserve all facial features,
clothing, and poses exactly. [Subject descriptions for context.]
```

### Era / Damage Type Modifiers

| Situation | Add to Prompt |
|-----------|---------------|
| Colorizing | "Add natural, realistic period-appropriate colors" |
| Keeping B&W | "Maintain black and white tones, do not colorize" |
| Teen/child subject | "The subject is a [teenage girl / young boy] — preserve smooth, youthful skin. Do not add wrinkles or age the subject." |
| Damaged face | "Reconstruct the [position] person's [face area] naturally based on surrounding facial structure" |
| Tintype / very dark | "Dramatically brighten and recover the underexposed image to reveal full detail" |
| Group photo | Describe all subjects: "Two women in back row and three young children in front row" |

---

## Step 3 — Set Parameters

| Parameter | Node | Value | Notes |
|-----------|------|-------|-------|
| FluxGuidance | FluxGuidance | **2.5–3.5** | 2.5 portraits, 3.5 heavy damage |
| Steps | KSampler | **20–28** | 20 clean, 28 heavy damage |
| CFG | KSampler | **1.0** | Do not change — Flux uses FluxGuidance |
| Sampler | KSampler | `deis` | |
| Scheduler | KSampler | `kl_optimal` | |
| Denoise | KSampler | **1.0** | Full regeneration |
| Sharpen sigma | ImageSharpen | **0.44–0.6** | 0.44 standard, 0.6 soft originals |
| Sharpen radius | ImageSharpen | **1** | |
| Sharpen alpha | ImageSharpen | **0.35** | |

### Guidance Quick Reference

| Photo Type | FluxGuidance | Steps |
|-----------|-------------|-------|
| Single portrait, light damage | 2.5 | 20 |
| Single portrait, moderate damage | 3.0 | 25 |
| Group photo (multiple faces) | 3.0 | 25 |
| Tintype / severe underexposure | 3.5–4.0 | 28 |
| Daguerreotype / heavy scratches | 3.5 | 28 |
| Colorization only (clean B&W) | 1.8–2.0 | 20 |

### Source Image Preparation

| Condition | Action |
|-----------|--------|
| Severely faded (content barely visible) | Provide contrast-boosted version — Flux invents proportions when it can't read structure (CUI-LL-011) |
| Good contrast but general softness/grain | Use as-is — upscale-only is sufficient |
| White/bright clothing on subject | Omit "white"/"bright" from prompt — causes halo artifact (CUI-LL-009) |

---

## Step 4 — Submit the Workflow

Use curl bypass (APP-LL-010) — `comfy_submit_workflow` returns HTTP 400 for complex workflows:

```powershell
$tmpFile = "$env:TEMP\comfyui_prompt.json"
[System.IO.File]::WriteAllText($tmpFile, "{`"prompt`":$prompt}")
curl.exe -s -X POST "http://127.0.0.1:8188/prompt" -H "Content-Type: application/json" -d "@$tmpFile"
```

Successful: `{"prompt_id": "xxx", "number": N, "node_errors": {}}` — empty node_errors = clean.

### API Health Check

```powershell
$test = '{"prompt":{"1":{"class_type":"VAELoader","inputs":{"vae_name":"ae.safetensors"}}}}'
curl.exe -s -X POST "http://127.0.0.1:8188/prompt" -H "Content-Type: application/json" -d $test
```

- `prompt_no_outputs` → API alive; problem is in your workflow JSON
- `400` from curl → check `node_errors` field
- `400` from `comfy_submit_workflow` but curl works → MCP wrapper issue; curl bypass correct

---

## Step 5 — Check Output

Output: `C:\ComfyUI\output\[filename_prefix]_*.png`

```powershell
curl.exe -s "http://127.0.0.1:8188/history" | ConvertFrom-Json | ConvertTo-Json -Depth 3
```

Look for `"status_str": "success"` and `"completed": true`.

---

## Step 6 (Optional) — ReActor Face Swap

Use when a face is too damaged for Flux to reconstruct and you have a reference photo.

1. Copy reference to `C:\ComfyUI\input\`
2. Add LoadImage node (200) for reference face
3. Add ReActorFaceSwap node (201) after ImageSharpen (194):

```json
"201": {
  "class_type": "ReActorFaceSwap",
  "inputs": {
    "enabled": true,
    "input_image": ["194", 0],
    "source_image": ["200", 0],
    "swap_model": "inswapper_128.onnx",
    "facedetection": "retinaface_resnet50",
    "face_restore_model": "GFPGANv1.4.pth",
    "face_restore_visibility": 1.0,
    "codeformer_weight": 0.5,
    "detect_gender_input": "no",
    "detect_gender_source": "no",
    "input_faces_index": "0",
    "source_faces_index": "0",
    "console_log_level": 1
  }
}
```

4. Update SaveImage (136) to receive from node 201

### Face Targeting in Group Photos

ReActor numbers faces left-to-right by detection order. Use `input_faces_index`: "0" (leftmost), "1" (second), "0,1,2" (multiple). Run with `console_log_level: 2` to identify order. Filter by gender: `detect_gender_input`/`detect_gender_source` = "male" or "female".

### Eye Assessment Before Inpainting

Closed/squinting eyes in outdoor snapshots are often a natural bright-light response (CUI-LL-013). Assess at full upscaled resolution before deciding to inpaint. Accept period-authentic expressions; only proceed if clearly a blink or damage artifact.

---

## Model Reference

| Node | Model File | Location |
|------|-----------|----------|
| UnetLoaderGGUF | `flux1-kontext-dev-Q4_K_M.gguf` | `C:\ComfyUI\models\diffusion_models\` |
| DualCLIPLoaderGGUF (clip1) | `clip_l.safetensors` | `C:\ComfyUI\models\text_encoders\` |
| DualCLIPLoaderGGUF (clip2) | `t5-v1_1-xxl-encoder-Q5_K_M.gguf` | `C:\ComfyUI\models\text_encoders\` |
| VAELoader | `ae.safetensors` | `C:\ComfyUI\models\vae\` |
| ReActorFaceSwap | `inswapper_128.onnx` | `C:\ComfyUI\models\reactor\` |
| Face Restore | `GFPGANv1.4.pth` | `C:\ComfyUI\models\facerestore_models\` |
