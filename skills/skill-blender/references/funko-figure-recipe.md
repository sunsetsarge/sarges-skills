# Custom Figure Recipe — photo → print-clean Funko-style vinyl (Bambu P1S)

The reusable, memory-persisted procedure for "design/build me a figure of X". Provenance:
Funko Sessions 1–4 (Hunyuan3D era, Confluence 36700202/37158913), Jaster Mereel build log
(66912390), convergence-loop post-mortem (73498626), Pixel Artistry local-3D-pipeline note
(82378754). Updated 2026-07-06 (audit + upgrade session).

## Stage 0 — Scope & IP check  `[judgment]`
- Confirm subject, target (print / render / game), size (default 95mm).
- "Funko Pop style" = the generic stylized-vinyl aesthetic: oversized head (~1:1 with body),
  black dot eyes, no mouth, simplified chunky limbs. Original figures only — no real logos,
  no Funko branding, flag Blaine before any sale/shipping use.

## Stage 1 — Reference images  `[mechanical: comfy jobs; judgment: pick winners]`
- Best: 2–4 user photos (front/side/three-quarter). Single photo works; multi-angle
  improves Trellis geometry.
- Generated: `comfyui-studio` skill → Z-Image Turbo or Qwen-Image. Prompt to the vinyl
  aesthetic, neutral A-pose/T-pose, plain background, full body in frame, even lighting.
- Background-strip with ComfyUI-RMBG if the image→3D model wants clean silhouettes.
- T-pose if the figure will ever be rigged; hand-held props generated separately
  (image→3D drops props from posed hands — Beachhead lesson: model props as separate
  meshes, attach in Blender).

## Stage 2 — Image → 3D  `[mechanical]`
**Primary (once installed): Trellis 2 GGUF via local ComfyUI.**
- Status 2026-07-06: NOT installed; ComfyUI-Manager `security_level` blocks API installs.
  Install = Blaine gate: set Manager security to allow, install the Trellis 2 GGUF node
  pack + models (fits 10GB VRAM in GGUF quant), export the workflow **as API JSON**
  (enable API nodes in ComfyUI settings) so agents can drive it headlessly.
- Disable texturing for print-only batches (mesh-only = faster).

**Fallbacks (live today, cloud credits):**
- `3d-ai-studio-api` skill → TRELLIS.2 (10–50 credits) or its miniature-figurine presets.
- `meshy-3d-generation` skill (defer to meshy-3d-printing for its own print flow).
- Rodin Gen-2.5 (rodin3d marketplace skill, unactivated) for hero-quality if ever needed.

**Retired — do not resurrect:**
- Photo → depth-map relief (.obj) React artifact: never real MiDaS (simulated HSV
  heuristic + Sobel), source lost, relief-only output. Superseded by Hunyuan3D (2026-04),
  then Trellis. If a flat-relief/lithophane need appears, that's a new decision.
- Cube-subdivide + shrinkwrap reconstruction (convergence loop): NEAREST bridges cavities
  (~0.9mm floor), PROJECT tears at arms/neck. Scripts remain in C:\Claude\Scripts as a
  reconstruction reference, not a generation path.

## Stage 3 — Blender import & cleanup  `[coding/mechanical]`
- Headless Blender 5.1 per SKILL.md survival rules (data-API scene clear, wm.* importers,
  identity OBJ axes, checkpoint .blend before destructive ops).
- AI meshes typically arrive: multi-component (junk islands), unscaled, sometimes Y-up.
  Normalize: join/isolate, orient Z-up, rough-scale.

## Stage 4A — PRINT branch (default)  `[mechanical; gate is blocking]`
Run the watertight gate:
```powershell
& "C:\Program Files\Blender Foundation\Blender 5.1\blender.exe" -b -P C:\Claude\Scripts\funko_print_prep.py -- `
  --input <mesh> --outdir <projectdir>\printprep --height 95 --voxel 0.35
```
- Pass criteria (all): non_manifold_edges=0, boundary_edges=0, degenerate_faces=0,
  loose_parts=1, trimesh is_watertight=True, volume>0.
- Retry cap 2 (voxel 0.35 → 0.5). Then STOP → hand fix.
- Slice via bambu-print / Bambu Studio: 0.1mm layers, tree supports (chin/hands),
  upright on bed, PLA default. Min wall 0.3mm is guaranteed by voxel ≥0.35mm.
- File convention: `D:\3D Printing\Things\Claude-generated\<Project>\<Name>_v<N>.stl`
  (binary), keep all versions, README.md with parameters (STL-protocol conventions).

## Stage 4B — RENDER/GAME branch (optional, never for print)  `[coding]`
- Retopo: Quad Remesher add-on if installed, else built-in QuadriFlow remesh.
- Bake high→low: normal + base color.
- **Gotcha (Pixel Artistry note): the eye area glitches when baking after Quad Remesher.
  1 retry max, then fix by hand — agent retry-loops burned sessions.**

## Stage 5 — Acceptance  `[judgment — top model]`
- Fidelity: renders vs reference images (front/side/3q EEVEE stills).
- Print-clean: printprep_report.json pass=true, independently re-verified (re-run the
  trimesh check yourself; never accept a subagent's prose claim).
- error_mean-style surface metrics are fidelity-only. They are BANNED as a sole
  done-judge (run3 lesson: 0.25mm mean with a torn, unprintable shell).

## Known-good numbers
| Parameter | Value | Why |
|---|---|---|
| Figure height | 95mm | House standard, matches Blank_Funko |
| Voxel remesh | 0.35mm (retry 0.5) | > P1S 0.3mm min wall; kills tears/non-manifold |
| Face budget post-gate | ≤ ~800k (decimate to ~500k if over, re-validate) | Slicer performance |
| Layer height | 0.1mm | Face detail priority |
| EPS surface error (fidelity) | mean < 0.30mm | From convergence-loop spec — fidelity only |
