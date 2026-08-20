---
name: skill-comfyui
description: "ComfyUI workflow management, photo restoration, prompt engineering, and CivitAI model downloads. Use this skill whenever the user mentions comfyui, workflow, node, face swap, stable diffusion, checkpoint, lora, sampler, image gen, photo restoration, flux kontext, civitai, download model, lora download, or checkpoint download. Also trigger when user discusses prompt engineering for image generation, DreamShaperXL, or antique photo colorization/repair. This skill covers the full ComfyUI pipeline from workflow submission to output validation."
---

# ComfyUI Protocol Skill

**Confluence sources for auto-sync:**

| Source Page | Page ID | Content |
|-------------|---------|---------|
| ComfyUI Protocol | 14647394 | Core rules, lessons learned, prompt guardrails |
| ComfyUI Image Restoration Workflow | 20250626 | Flux Kontext operating instructions |
| MCP: CivitAI | 18120724 | Download rules, token auth, validation |

**Last synced:** 2026-04-17 | **Source versions:** ComfyUI Protocol v4.0, Restoration Workflow v1.0, CivitAI v1.1

## Environment note
Paths like C:\... and D:\... are Blaine's Windows machine. In a remote/Cowork Linux session, reach them via the remote-device tools (device_bash / Desktop Commander), never the local Bash tool. Ports and paths were verified on the Windows box only. Any 'Last synced' tables are provenance only — do not attempt to sync; if a rule conflicts with observed reality, trust reality and flag for re-sync.

> Routing: model selection, prompt expansion, and generation templates now live in the `comfyui-studio` skill — it is the source of truth for what's installed and how to run it. This skill owns submission plumbing, photo restoration, and CivitAI downloads only.

---

## Before Starting Any ComfyUI Task

1. Check the Lessons Learned Index below — many errors have already been solved
2. Confirm workflow file location: `C:\ComfyUI\` or user-specified path
3. For photo restoration: read `references/photo-restoration.md`
4. For prompt engineering (DreamShaperXL, composition): read `references/prompt-engineering.md`
5. For CivitAI model downloads: read `references/civitai-downloads.md`

---

## Lessons Learned Index (CHECK FIRST)

| ID | Lesson |
|----|--------|
| CUI-LL-001 | Never trust `comfy_submit_workflow` return value — always verify via `/history/{prompt_id}` |
| CUI-LL-002 | Never use curl for Windows HTTP POSTs — use Python `urllib.request` instead |
| CUI-LL-003 | DreamShaperXL + OldAnimeStyle LoRA skews feminine — apply masculine weight boosting and negatives |
| CUI-LL-004 | Large horns trigger exposed-skull/undead face — negate and use T-shaped visor language |
| CUI-LL-005 | DreamShaperXL + OldAnimeStyle defaults to bust composition — use tall resolution + explicit full-body weights |
| CUI-LL-006 | Flux Kontext: denoise MUST stay at 1.0 — ReferenceLatent handles image anchoring, not denoise |
| CUI-LL-007 | Flux Kontext: chaining generation passes causes hallucination — fabric/texture invented at guidance 1.6+; use upscale-only for second pass |
| CUI-LL-008 | Flux Kontext: colorization requires guidance >=1.8 but reintroduces artifacts — single-pass only; no chaining |
| CUI-LL-009 | Flux Kontext: avoid "white" or "bright" in subject description — causes white halo artifact around subject edges |
| CUI-LL-010 | Flux Kontext: upscale-only (4x-UltraSharp + light ImageSharpen) is safer than a second Flux generation pass — zero hallucination risk |
| CUI-LL-011 | Flux Kontext: severely faded photos cause proportion hallucination — provide contrast-boosted source image |
| CUI-LL-012 | ComfyUI native graph format: use `"mode": 4` to bypass a node by default — activates via right-click Bypass toggle |
| CUI-LL-013 | Closed/squinting eyes in outdoor snapshots may be natural bright-light response — assess at full resolution before inpainting |
| CUI-LL-014 | CivitAI `get_model_version` fails with schema error when model description is null — use `web_fetch` on civitai.com page instead |
| CUI-LL-015 | Model directory stub-detection scripts must filter by filename pattern, NOT blanket file size — small files can be legitimate |

---

## Workflow Submission Rules

### MCP Tool Verification (CRITICAL)

`comfy_submit_workflow` performs pre-validation that does NOT accurately reflect ComfyUI's actual queue/execution state. It can return `Workflow validation failed` even when the job succeeds.

**After every submission:**

1. Capture the `prompt_id` from the MCP response
2. Query `/history/{prompt_id}` directly to confirm actual execution status
3. Use `comfy_wait_for_completion` as a supplement, not a substitute

### HTTP Requests to ComfyUI API (Windows)

**Never use bare `curl`** — in PowerShell it aliases Invoke-WebRequest with different quoting. `curl.exe` (the real binary, used in the bypass below) is fine; the rule is about the alias, not the tool.

**Always use Python:**

```python
import urllib.request, json
data = json.dumps(payload).encode('utf-8')
# Server runs on port 8000 (the comfyui MCP is pinned there); 8188 only appears
# when ComfyUI is relaunched wrong — see comfyui-studio.
req = urllib.request.Request('http://127.0.0.1:8000/prompt', data=data,
      headers={'Content-Type': 'application/json'})
urllib.request.urlopen(req)
```

### Complex Workflows — Curl Bypass

For complex multi-node JSON that `comfy_submit_workflow` rejects with HTTP 400 (APP-LL-010):

```powershell
$tmpFile = "$env:TEMP\comfyui_prompt.json"
[System.IO.File]::WriteAllText($tmpFile, "{`"prompt`":$prompt}")
# Server runs on port 8000 (the comfyui MCP is pinned there); 8188 only appears when ComfyUI is relaunched wrong — see comfyui-studio.
curl.exe -s -X POST "http://127.0.0.1:8000/prompt" -H "Content-Type: application/json" -d "@$tmpFile"
```

### Image Upload Rule

**Never use `comfy_upload_image`** — it targets the Electron app's input folder, invisible to the standalone API at port 8000 (APP-LL-009). Always copy directly:

```powershell
Copy-Item "F:\path\to\source.jpg" "C:\ComfyUI\input\source.jpg" -Force
```

### Optional Node Pattern (Bypass)

To add a node that is off by default: set `"mode": 4` in the node definition. Keeps all links wired; user activates via right-click > Bypass toggle. Use teal color (`"color": "#243", "bgcolor": "#465"`) and a MarkdownNote to explain the toggle.

---

## Workflow Help Checklist

When assisting with ComfyUI workflows:

- Ask for the specific node or error before troubleshooting
- Request the workflow JSON if diagnosing a complex issue
- Reference checkpoint/LoRA names exactly as they appear in the models folder
- Query `/object_info` API before building workflow JSON to confirm node signatures

---

## Common Issue Checklist

| Issue | First Check |
|-------|-------------|
| Node not found | Custom nodes installed? Restart ComfyUI after install |
| Model not loading | File in correct `/models/` subfolder? |
| CUDA out of memory | Reduce resolution or batch size |
| Face swap failing | Insightface installed? Correct model selected? |
| Workflow won't queue | Check for disconnected required nodes |
| MCP reports failure | Check `/history/{prompt_id}` — may have succeeded anyway |
| Feminine features on male character | Apply CUI-LL-003 guardrails (see prompt-engineering.md) |
| Skull face instead of visor | Apply CUI-LL-004 guardrails (see prompt-engineering.md) |
| Half-body instead of full body | Apply CUI-LL-005 guardrails (see prompt-engineering.md) |
| White halo around subject | Remove "white"/"bright" from subject description (CUI-LL-009) |
| Hallucinated fabric/skin texture | Stop chaining Flux passes — upscale-only for pass 2 (CUI-LL-007) |
| Wrong body proportions in restored photo | Use contrast-boosted source image (CUI-LL-011) |
| `get_model_version` throws schema error | Model has null description — use web_fetch instead (CUI-LL-014) |
| Stub-detection flags wrong files | Script uses blanket size filter — fix to filename pattern (CUI-LL-015) |

## Error Logging

Log ComfyUI errors to Application Errors page (Confluence ID: 655375) using standard error format.

## Output Storage

Generated images save to: `C:\Claude\Image_Output\`

## GGUF Models Reference

- Flux: `flux1-kontext-dev-Q4_K_M.gguf`
- T5: `t5-v1_1-xxl-encoder-Q5_K_M.gguf`
- **Warning:** `t5-v1_1-xxl-encoder-Q8_0.gguf` does NOT exist locally — always use Q5_K_M
