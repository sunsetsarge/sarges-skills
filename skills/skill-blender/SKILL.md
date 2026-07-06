---
name: skill-blender
description: >-
  Agentic Blender for print-clean 3D results — drive Blender headless or via the
  BlenderMCP TCP bridge to import/generate/clean AI meshes, run the watertight
  print-prep gate (voxel remesh + manifold validation), and follow the Funko-style
  custom figure recipe (photo → image gen → Trellis 2 image-to-3D → Blender cleanup →
  Bambu P1S export at ~95mm). USE whenever the user says Blender, "design/build me X
  in Blender", custom figure / figurine / Funko-style vinyl, make a mesh watertight /
  manifold / print-clean, mesh repair, voxel remesh, retopology, Quad Remesher,
  normal/texture baking, or wants an AI-generated 3D model made printable. NOT for:
  programmatic trimesh part design (skill-3d-printing), plain image generation
  (comfyui-studio), cloud 3D generation APIs (meshy-3d-generation / 3d-ai-studio-api),
  or slicing/sending prints (bambu-print / meshy-3d-printing) — this skill hands off
  to those at the boundaries.
---

# skill-blender — Agentic Blender & Print-Clean Pipeline

**Prime directive: no mesh leaves this skill for a slicer unless the watertight gate passed.**
A fidelity metric (error_mean, "looks right") is NEVER sufficient to call a mesh done — the
2026-06-24 convergence-loop run hit its 0.25mm error target with a torn, unprintable shell.
Fidelity and print-clean are two separate, both-blocking acceptance checks.

## How to drive Blender

| Mode | When | How |
|---|---|---|
| **Headless (primary for automation)** | Batch work, validation, unattended runs | `& "C:\Program Files\Blender Foundation\Blender 5.1\blender.exe" -b -P <script.py> -- <args>` |
| **TCP bridge (interactive)** | Blaine has Blender open with the BlenderMCP addon | `C:\Claude\Scripts\blender_tcp.py` → socket 127.0.0.1:9876. Envelope MUST be NUL-terminated `{"type":"execute","code":...,"strict_json":false}` (top-level `code`; `execute_code` silently times out) |

Use **Blender 5.1** (4.3 also installed; the MCP addon needs 5.1+).

## Blender 5.x survival rules (hard-won — do not re-derive)

1. **Scene reset**: clear via data API (`bpy.data.objects.remove(o, do_unlink=True)` + `bpy.ops.outliner.orphans_purge`). `read_factory_settings`/`read_homefile` are blocked in the addon sandbox and tear down headless context.
2. **Import/export**: `wm.stl_import`/`wm.stl_export` (legacy `import_mesh.stl` removed), `wm.obj_import`/`wm.obj_export` with `up_axis='Z', forward_axis='NEGATIVE_Y'` (identity — default rotates Z-up to Y-up and breaks world-Z logic). No 3MF importer exists: Bambu 3MF is a zip — parse `3D/Objects/object_*.model` XML directly.
3. **Booleans on big organic meshes**: solver `'MANIFOLD'` only. EXACT silently collapsed a 197k-face body to <1k faces. Self-intersecting compound shells: voxel-remesh them into one clean operand first.
4. **Checkpoint before every destructive phase** (`wm.save_as_mainfile` to `iter_N.blend`). Ops on multi-million-vert meshes fail late and unrecoverable.
5. **Never take viewport screenshots** (always black headless) — verify with counts, bounds, and bmesh stats, or render EEVEE stills.
6. **Blender STL export of multi-part joins is a trap**: `object.join()` doesn't merge geometry; overlapping internal faces slice as zero-volume. Either voxel-remesh after joining or build the part programmatically (that path belongs to skill-3d-printing).
7. **`wm.stl_export` needs `export_selected_objects=True` + explicit `obj.select_set(True)`** — otherwise you silently export empty/wrong geometry. And `mesh.separate(type='LOOSE')` leaves the active object ambiguous — re-set `view_layer.objects.active` after it.
8. **Never trust external face counts** — the 5.1 STL importer silently dedupes triangles ("Removed N duplicate triangles"); always re-measure counts in-script.

## The watertight print-prep gate

`C:\Claude\Scripts\funko_print_prep.py` (headless):

```powershell
& "C:\Program Files\Blender Foundation\Blender 5.1\blender.exe" -b -P C:\Claude\Scripts\funko_print_prep.py -- `
  --input <mesh.stl|.obj> --outdir <dir> --height 95 --voxel 0.35
```

Pipeline: import → fill holes → **voxel remesh** (voxel in real-mm at target height) → keep largest
shell → recalc normals outside → validate → scale to height, seat z=0 → **binary STL** +
`printprep_report.json`.

**Pass requires**: non_manifold_edges=0 · boundary_edges=0 · degenerate_faces=0 · loose_parts=1 ·
trimesh cross-check `is_watertight=True`, volume>0, winding consistent.

**Retry cap: 2** (0.35mm → 0.5mm voxel). Still failing → STOP and flag for a hand fix in Blender.
Do not loop remesh/bake/repair steps hoping — looping burned entire sessions before.
Independently re-verify any subagent's pass claim by re-running the trimesh check on the artifact.

## The custom-figure recipe (Funko-style)

Full recipe with stage-by-stage details: `references/funko-figure-recipe.md`. Summary:

1. **Reference images** — user photos (multi-angle best) and/or `comfyui-studio` (Z-Image/Qwen) stylized to the *generic* big-head, black-dot-eye vinyl aesthetic. **IP guardrail**: original figures only; flag Blaine before anything carries Funko branding or is sold.
2. **Image → 3D** — Trellis 2 GGUF in ComfyUI (local, free) once installed; until then `3d-ai-studio-api` TRELLIS.2 or `meshy-3d-generation` (cloud credits). *Retired paths — do not resurrect*: photo depth-map relief (never real MiDaS; superseded 2026-04), cube-shrinkwrap reconstruction (tears at cavities; reference technique only).
3. **Blender cleanup** — import per rules above.
4. **Branch**: **PRINT (default)** → watertight gate → P1S export. **RENDER/GAME (optional)** → retopo (Quad Remesher if installed, else built-in QuadriFlow) + bake high→low (normal + base color). *Gotcha*: eye-area bake glitches (Quad Remesher issue) — 1 retry max, then hand fix. Never run the bake branch for print jobs (single-color FDM ignores textures).
5. **Accept** only on fidelity AND gate-pass.

## Bambu P1S constraints (bake into every export)

| Constraint | Value |
|---|---|
| Build volume | 256×256×256mm (figures ~95mm — never near limit) |
| Nozzle / layer | 0.4mm / 0.1mm (face-detail priority) |
| Min wall | **0.3mm** (3 layers) — voxel remesh ≥0.35mm respects this |
| Materials | PLA / PETG / ABS |
| Orientation | Upright, feet/base on bed, seated z=0 |
| Supports | Tree, for chin/hands overhangs |
| STL format | Binary (Claude Code sessions; ASCII rule was Desktop-era) |

## Model tiers (for orchestration)

- **Judgment** (accept a figure, change this recipe, aesthetic review): session's top model.
- **Coding** (scripts, skill edits): Sonnet.
- **Mechanical** (batch remesh runs, comfy jobs, file plumbing): Haiku/Sonnet.
- Executor prompts must forbid the Agent tool (delegation-spiral lesson).
