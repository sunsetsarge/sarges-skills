---
name: game-asset-pipeline
description: Turn raw generated art into engine-ready game assets — sliced sprite atlases with a manifest, or 3D models pre-rendered to sprite sheets — with the verification discipline that stops halos, jitter, wrong-facing characters and unreadable silhouettes from shipping. Two lanes, 2D and 3D, sharing one production spine. USE THIS SKILL whenever the user has (or is about to have) generated art that must become usable game assets: ChatGPT/DALL-E/Midjourney character sheets, sprite sheets, walk cycles, a Meshy or Tripo GLB, a Blender model destined for a 2D game, or a folder of PNGs to get into an engine. Trigger on "slice this sprite sheet", "get these sprites into my game", "build a sprite atlas", "make a sprite sheet from this model", "my sprites have white edges/halos", "my walk cycle jitters", "my character faces the wrong way", "render this GLB to a sprite", "the sprite looks pixelated", "how do I package these frames", and on any asset-pipeline, asset-ingestion, or spritesheet-packing request — even when no tool is named. This skill sits ABOVE the tool-level skills: pixel-art-studio and comfyui-studio GENERATE art, meshy-3d-generation and skill-blender drive those tools; this one is the production line and the failure modes that turn their output into shipped assets. NOT for generating pixel art from scratch (pixel-art-studio), and NOT for 3D printing (meshy-3d-printing).
---

# Game Asset Pipeline

Generated art is not a game asset. Between them sits a production line, and every
step of it has a failure mode that looks fine in a thumbnail and wrong in motion.

This skill is that production line. It has two acquisition lanes that converge on
the same output: **trimmed PNG frames → packed atlas → manifest → verified in-engine.**

Everything here was learned by shipping. The rules exist because something broke.

## Pick the lane first

| Your source art is… | Lane | Read |
|---|---|---|
| A grid sheet of poses on a white/near-white background (ChatGPT, DALL-E, Midjourney) | **2D** | `references/lane-2d-sheets.md` |
| A 3D model — Meshy/Tripo GLB, or anything in Blender — for a 2D engine | **3D** | `references/lane-3d-render.md` |
| Already-trimmed PNG frames from anywhere | **skip to packing** | `references/lane-2d-sheets.md` §Stage B |

The 3D lane **ends where the 2D lane's packing step begins**. A GLB rendered to
frames is just frames; feed them to `scripts/lane-2d/sync_assets.py` to get an
atlas and manifest. Do not treat the lanes as alternatives — they are stages of one
conveyor, and a project often uses both.

Then read `references/renderer-contract.md` before writing any draw code. It covers
the manifest shape and the Canvas-2D rules that decide whether the asset reads on
screen at all.

## The spine — true in both lanes

These are the rules that do not care whether the art came from a diffusion model or
Blender. Internalise these five; the lane files carry the rest.

**1. Orientation must match motion, and you must verify it from a zoomed crop.**
Whatever end of the thing moves first on screen must point that way in the asset.
In 2D this is the facing convention baked at pack time; in 3D it is the camera
azimuth. Both fail the same way: fine in a still, backwards in motion.

**A caption is not evidence, even when it agrees with you.** Filenames, row labels and
text baked into the sheet are all unreliable, and the failure mode that actually bites
is the caption that *seems* to confirm your reading. Real example: `Orc_Axeman_Sprites.png`
has "WALK LEFT" printed beside a row of orcs facing **right**. An agent with this skill
loaded still concluded "faces left — matching their captions", and would have un-mirrored
three correct enemies into facing backwards.

The only sound method: crop one frame, blow it up, and find an unambiguous feature —
nose, tusks, eye, gun barrel, the dog's tail. Decide from that. If a mirror has already
been baked, put the raw frame and the packed frame side by side; source-facing is then
provable rather than arguable.

**2. Trim multi-frame and multi-part output with ONE SHARED UNION BBOX.**
The single most expensive rule in this file, and it bites both lanes identically.
Trim each frame to its own alpha box and the anchor moves frame to frame: a walk
cycle jitters, or a turret overlay drifts off its hull. Compute the union box across
every frame (and every part) of an animation, crop them all to it, draw them all at
the same destination rect. This makes drift structurally impossible instead of
something you tune away. Watch for baked drop shadows — they are usually why a
per-frame box moves.

**3. Decide the on-screen size first, then source at 2–3× it. Never upscale.**
Downscaling stays crisp; upscaling is what makes an asset read as "pixelated", and
that is almost always the *art's* resolution, not your code. Check the native frame
height before spending any time in code. Corollary: detail below your on-screen size
is wasted prompt effort.

**4. Look at your own output, at real size, before claiming it works.**
You are vision-capable. Render a contact sheet and actually read it. Then verify in
the running engine at the real device resolution — not a desktop window. For anything
important, have a *different model* judge a screenshot against explicit acceptance
criteria; self-review misses defects, and a subagent's prose claim that it worked is
not evidence. See `references/verification.md`.

**5. Before you condemn the art, check whether your TOOL failed.**
A derived artefact is not evidence about its source. Broken slicer output and genuinely
bad art look identical downstream, and the cheap, wrong conclusion is "regenerate this."
**Open the original sheet and look at it** before writing a single REGEN_TODO entry.

This has real teeth. On the reference project three sheets were written off as
"turntables, unusable, needs regeneration" — the call was inherited from a previous
session and confirmed by inspecting the *slicer's* output. Opening the source sheets
showed all three were excellent: clean labelled grids, one an 8-direction × 5-animation
layout with a perfectly good 4-frame left-facing walk sitting in it. The art was never
the problem; a blob-detector had merged the row-label margin into the artwork. Two
enemies and a boss were cut from the game for nothing.

**6. Never stall on art that genuinely cannot be used.**
Once you have confirmed the source really is unusable, log it with a concrete
regeneration spec, substitute a loud magenta placeholder, design around the gap, and
keep moving. A logged known-issue beats a blocked pipeline.
Template: `references/REGEN-TODO-template.md`.

## Standard workflow

1. **Enumerate the real filesystem.** Read the directory tree; never guess filenames.
   Write the real paths into the job spec.
2. **Inspect before generating anything expensive.** 2D: is that row an animation or a
   camera turntable? 3D: is the GLB one fused mesh, and which axis is forward?
3. **Author a job spec** — a data file naming, per asset, which row/angle is which
   animation, its source facing, and its on-screen height. Authored data driving a
   deterministic build script beats a clever auto-detector; the detector will be wrong
   on one sheet in ten and you will not notice.
4. **Build** with the bundled script for the lane.
5. **Look at the contact sheet.** Halos, clipped edges, baseline drift and turntables
   are only visible here.
6. **Install + wire into the engine's data**, then verify in the running game.
7. **Log gaps** in REGEN_TODO, decisions in DECISIONS.md.

## Bundled scripts — copy these, don't rewrite them

Working code beats a description of working code. All paths relative to this skill.

**Lane 2D** (`scripts/lane-2d/`) — Python 3.10 + Pillow:

| Script | Does |
|---|---|
| `cut_cells.py` | **Start here for any generated sheet.** Sheet → equal-size cells that never crop a sprite: finds the sprites first, sizes one cell to the largest, places each on a shared anchor (`center` or `bottom`). Strips grid lines and labels, keys any flat matte, `--split` exports loose debris pieces, `--size` downscales, writes manifest + dark contact sheet. Works on any path |
| `slice_sheet.py` | Sheet → per-frame PNGs. Matte detection, row bands, frame clustering, caption stripping. Modes `grid` / `gaps` / `auto` |
| `sync_assets.py` | Frames → one WebP grid per character + `manifest.json`. Union crop, facing bake, uniform scale, defringe |
| `ase_pack.py` (+ `ase_pack.lua`) | Equal-size frames or an equal-cell sheet → Aseprite source file + RGBA sheet + Aseprite JSON, by running Aseprite headless. Named animation tags with direction and timing, optional palette lock (`--palette nes` or `--max-colors N`), anchor slice, `--defringe` to strip a light halo left by a generator. Use instead of `sync_assets.py` when the engine reads Aseprite JSON or the art should stay editable. Verifies its own output; `ase_pack_selftest.py` runs 12 tests. See `references/lane-2d-sheets.md` §Stage B-alt |
| `audit_facing.py` | One labelled crop per character so facing can be read by eye |
| `zoom_check.py` | High-zoom N-frames-per-row view. Settles facing arguments |
| `contact_row.py` | Every frame of a row with indices. Exposes turntables |
| `qa_packed.py` | Zoomed QA of the **packed** output with a ground-anchor line drawn |

**Lane 3D** (`scripts/lane-3d/`) — Blender headless + Meshy API:

| Script | Does |
|---|---|
| `run_battleship.py` | Cleanest single-model Meshy generator (preview → refine → download). Change only the prompt |
| `run_bomber.py` | Same, two models in one run. The multi-asset template |
| `inspect_battleship.py` | **Run first on every GLB.** Mesh count, verts, bbox, longest axis |
| `build_bomber_sprite.py` | Single still with explicit elev/az/roll. Best for hunting a camera angle |
| `render_frames.py` | Config-driven headless renderer: animation sampling, per-unit azimuth, bbox-fit camera |
| `postprocess.py` | Alpha trim with the shared union bbox (spine rule 2) |
| `split_render.py` | Split a fused GLB into base + part via bmesh centroid |
| `inspect_bones.py`, `probe_hands.py` | Rig inspection; attaching props Meshy dropped |
| `build_lcvp.py`, `build_lst.py` | Building a shape from Blender primitives when the generator refuses it |

## Environment on this machine

| Thing | Where |
|---|---|
| Python (Pillow, requests) | `C:\AI-Shared\python.exe` — 3.10, **not** on PATH as `python` |
| Blender headless | `C:\Program Files\Blender Foundation\Blender 5.1\blender.exe` (4.3 also present) |
| Meshy API key | `C:\Claude\.credentials\meshy.key`, or `MESHY_API_KEY`. Base `https://api.meshy.ai` |
| Reference 2D implementation | `C:\Terrorier\longnight` (Blackpaw: The Long Night) |
| Reference 3D implementation | `C:\Claude\Projects\Active\Beachhead\meshy_test` (SHORE PATROL) |

Meshy costs ~20–40 credits per model (preview + refine); check `GET /openapi/v1/balance`.
GLBs are 10–22 MB — gitignore them, keep the rendered PNGs, and download immediately
because Meshy's server copies expire in about three days.

## What "done" looks like

- A manifest the engine consumes, with real paths read off disk.
- Contact sheets you have personally looked at.
- Every animation proven to load and play in the engine, ideally with a
  machine-readable pass/fail so a headless run can exit non-zero.
- `REGEN_TODO.md` for anything unusable, each entry with a regeneration spec.
- A short `DECISIONS.md` note for anything you decided without the user.
