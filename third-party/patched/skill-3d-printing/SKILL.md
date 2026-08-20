---
name: skill-3d-printing
description: "3D printing, STL geometry, and mesh operations with trimesh, Blender, and Bambu Lab printers. Use this skill whenever the user mentions 3d print, stl, bracket, blender, trimesh, mesh, boolean, cubicle shelf, dashcam, bambu mcp, snap fit, dovetail, interlocking, or any geometry/CAD design task. Also trigger for Bambu Lab printer status checks, print monitoring, or any task involving STL file creation, modification, or validation. This skill contains 25 hard-won rules from real session failures — following them prevents the most common geometry and workflow errors."
---

# 3D Printing & STL Geometry Skill

**Confluence sources for auto-sync:**

| Source Page | Page ID | Content |
|-------------|---------|---------|
| Master Prompt Hub (APP-LL-018 section) | 786433 | All 25 geometry rules |
| Session Lessons — CubicleShelf Dovetail | 34209793 | Dovetail design errors |
| Prompt Tree Analysis — Error Patterns | 35160065 | Error pattern analysis |
| Session Lessons — Nameplate Holder | 35487745 | Comment sketch methodology |
| Session Lessons — Reference Model | 35848193 | Scale/dimension lessons |

**Last synced:** 2026-04-17 | **Source version:** Master Prompt Hub v23.0

## Environment note
Paths like C:\... and D:\... are Blaine's Windows machine. In a remote/Cowork Linux session, reach them via the remote-device tools (device_bash / Desktop Commander), never the local Bash tool. Ports and paths were verified on the Windows box only. Any 'Last synced' tables are provenance only — do not attempt to sync; if a rule conflicts with observed reality, trust reality and flag for re-sync.

---

## The 25 Rules (Apply to Every Geometry Session)

### Boolean & Mesh Integrity

**Rule 1 — Never declare a boolean result "single solid" without a connectivity check.**
Always run `networkx nx.connected_components()` on `result.edges_unique` after every boolean. Anything > 1 component = failure.

**Rule 2 — Always use earcut for concave polygon triangulation.**
`mapbox_earcut.triangulate_float32(verts2d, rings)` for any polygon with a concave angle or more than 4 vertices.

**Rule 3 — Never use Blender booleans on complex STL geometry.**
Use trimesh + `engine='manifold'` exclusively.

**Rule 5 — Boolean overlap offsets must be in a non-visible direction — offsets into a visible face leave seams and steps on the finished print.**

**Rule 6 — Adjacent sections must share volume, not just an edge.**
Ensure >=2mm volumetric overlap perpendicular to the shared face.

**Rule 7 — Validate profile polygons with shapely before extruding.**
`shapely.geometry.Polygon(profile).is_valid` must be True.

### Spatial Awareness & Coordinates

**Rule 4 — Map peg holes to coordinates before placing any feature.**
Run vertex cluster analysis and annotate in code before placing any arm, pillar, or feature.

**Rule 8 — Re-check feature locations after every coordinate transform — transforms silently move features, and stale coordinates have placed holes and arms in the wrong spot.**

**Rule 9 — Label hook/clip vertices explicitly before coding — unlabeled vertices lead to guessed placement and features rebuilt multiple times.**

**Rule 10 — Apply all transforms to original STL in one operation.**

### Design Process

**Rule 12 — For interlocking connectors, require a sketch before building — unsketched dovetails have been built mis-mated and had to be reprinted (see CubicleShelf Dovetail lessons).**

**Rule 13 — Clarify "reinforce/thicken" scope before implementing — guessing the scope has thickened the wrong faces and forced full rebuilds.**

**Rule 24 — Ask design intent questions before building any new feature type.**
Ask 1–3 scoped questions: (1) Open or enclosed? (2) Retention — rails, lip, snap, friction? (3) Dimension preference? Ask ONCE per feature type per session.

**Rule 25 — Write a comment sketch before coding any retention feature.**
Before coding any lip, rail, snap, clip, or overhang, write a comment block:
```python
# From aisle: [top rail Xmm] [open window Ymm] [bottom rail Xmm]
# Top lip: Y=A–B, Z=C–D — inset Xmm from front face
```
Map every bound to a named coordinate before writing any box() call. One comment sketch = one correct build. Four guesses without a sketch = ~15,000–20,000 wasted tokens.

### Communication Protocol

**Rule 21 — Output a spatial targeting statement before every boolean or geometry modification.**
`→ Target: [face name], [coordinate], normal=[direction], [action]. Proceeding.`
This is a declaration, not a question. User can interrupt in one word.

**Rule 22 — Ambiguous spatial message: state interpretation, then act. Never reason >2 steps internally.**
OPTION A: State interpretation in one line and proceed. OPTION B: Ask one scoped question. Never exceed 2 internal reasoning steps before externalizing.

**Rule 23 — Repeated complaint within 2 messages: check for timing overlap before re-investigating.**
If a complaint looks identical to the last one, check whether a correction was already in-flight. State it and confirm.

### STL File Delivery

**Rule 15 — STL file delivery: always gen script + local Python execution. Never chunked text writes.**
Workflow:
1. Write gen script via Filesystem MCP
2. Run via the verified interpreter `C:\AI-Shared\python.exe` (miniconda path is legacy; the `python3` stub on this machine is broken — per Skills Maintenance PLAN D4). If neither exists, ask before guessing.
3. Verify: `python -c "import trimesh; b=trimesh.load(path,force='mesh'); print(b.is_watertight, len(b.faces))"`
4. If miniconda lacks a package: `python -m pip install [package]` then re-run

**Rule 11 — For geometry sessions, fetch only the one Confluence project page for the current build (a "sprint page") — never the whole Master Prompt Hub. Why: bulk fetches burned 30-50% of context before any geometry was written.**

### Bambu Lab & Hardware

**Rule 14 — Always read HMS error codes from the photo, never verbal description — verbally relayed HMS codes have been transposed and wasted whole debug sessions.**

*(Rule 16 removed — UniFi routing lives in ez-unifi)*

**Rule 17 — Check MCP server log before diagnosing "Could not attach."**

**Rule 18 — Empty response from bambu_get_status = printer is off.**

### Blender-Specific

**Rule 19 — Never call the Blender viewport screenshot tool.**
Always returns black. Use vertex/face coordinates or bounding box instead.

**Rule 20 — Never import a /mnt/ container path into Blender.**

---

## Pre-Build Checklist

Before writing any geometry code:

1. Read or confirm the reference STL dimensions
2. Run Rule 24 design intent questions (if new feature type)
3. Write Rule 25 comment sketch (if retention/snap/lip feature)
4. Output Rule 21 spatial targeting statement
5. Confirm approach with user before coding

## Post-Build Validation

After every geometry operation:

1. Rule 1: connectivity check (`nx.connected_components`)
2. Rule 7: polygon validity (`shapely is_valid`)
3. Rule 15: watertight check (`trimesh is_watertight`)
4. Rule 8: coordinate verification after transforms
