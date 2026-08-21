# Lane 3D — model → pre-rendered sprite

Text prompt → Meshy text-to-3D (GLB) → headless Blender render to PNG frames → trim →
install. **The game engine stays 2D.** Every "3D model" in the shipped game is a
pre-rendered sprite; there is no runtime 3D.

This is the right architecture when you want 3D-looking assets on an HTML5 canvas or
2D engine and you do not want a WebGL renderer, physics, or a 40 MB model payload.

Hardened on SHORE PATROL (`C:\Claude\Projects\Active\Beachhead\meshy_test`).

---

## The steps

1. **Generate.** Copy `run_battleship.py`, swap the prompt, run with `MESHY_API_KEY`
   set. It does `mode:"preview"` → poll → `mode:"refine"` (with `preview_task_id`,
   `enable_pbr:true`) → poll → download GLB + thumbnail. **Check the thumbnail before
   spending render time.** `run_bomber.py` is the two-model template.
2. **Inspect.** `blender -b -P inspect_battleship.py -- model.glb` → mesh count, per-
   object verts, bbox, longest axis. This tells you whether parts can be separated and
   which way the model faces. Run it on every new GLB before promising any behaviour.
3. **Find the camera angle by montage.** Render 3–4 candidate elev/az values with
   `build_bomber_sprite.py`, montage them side by side, and pick. Do not guess a single
   angle — see Rule 1.
4. **Render final.** Single still, or `render_frames.py` with a JSON config for
   animation frames / multiple azimuths:
   `blender -b -P render_frames.py -- config.json` (see `example_render_config.json`).
5. **Trim + install.** Alpha bbox + 4–8px pad, scale to target height (LANCZOS), write
   into `assets/`. Use `postprocess.py`'s shared-bbox logic for base+part pairs.
6. **Wire + verify.** Register the path so it preloads, reference it from data JSON,
   screenshot the running game, and have a different model judge it.

From here the frames are just frames — hand them to `scripts/lane-2d/sync_assets.py`
if you want them packed into an atlas with a manifest.

---

## The rules — this is the actual value

**Rule 1 — The camera angle must match how the object MOVES on screen.**
The #1 time sink. Render the object as the player sees it in motion, not as a product
shot. On SHORE PATROL the bomber was rendered from straight below (elev −88): a
perfect belly view that read as the plane sliding in belly-first, and was rejected on
sight. Re-rendering at elev −40 (front-3/4 from below) put the nose leading the
direction of travel and it read correctly. Rule of thumb: whatever end moves first must
point that way in the sprite. Enemies advancing toward a bottom-screen player → render
head-on, az ~270–290.

**Rule 2 — Meshy models arrive as ONE FUSED MESH. You cannot rotate sub-parts.**
The SHORE PATROL battleship was a single 152k-vertex mesh; the turrets were not
separable objects. Any plan depending on "rotate just the turret" needs `split_render.py`
(geometric split by centroid) or a separately generated part. Verify with
`inspect_battleship.py` *before* promising that behaviour.

**Rule 3 — A side/broadside sprite cannot show guns aimed at the camera.**
A geometry wall, not a tuning problem. Three attempts (aim-at-camera, aim-down,
aim-down-forward) all foreshortened into ugly poles. Either render at 3/4 from the
start, or accept the broadside read and sell aggression with muzzle flashes and tracer
origins instead of barrel direction. Never stick flat 2D vector shapes (canvas `lineTo`
barrels) on a photoreal render — it looks terrible and was rejected on sight.

**Rule 4 — The generator refuses certain shapes; build those from primitives.**
Open-well / concave craft (Higgins boat, LST with bow doors) failed twice on Meshy. The
fix was `build_lcvp.py` / `build_lst.py` — assembling the shape from Blender primitives
in a script. Faster than fighting the generator. Symptom: it comes back as a generic
closed hull.

**Rule 5 — Rigged/T-pose models silently DROP hand-held props.**
Ask for "soldier holding a rifle" and you get empty hands (~90 credits to learn). Fix:
attach the prop procedurally in Blender from the hand bone matrix (`probe_hands.py`,
`inspect_bones.py`). The hand-to-hand grip line is diagonal, **not** the aim axis — aim
along character-forward, and `transform_apply` before using `matrix_world`.

**Rule 6 — Base + part sprites MUST share ONE UNION BBOX.**
Trim a hull and its turret independently and their alpha bboxes differ, so the overlay
drifts. Compute the union across all frames and parts, crop everything to it, draw both
at the identical destination rect. `postprocess.py` implements this. It is what makes
part-compositing pixel-locked. (Same rule as the 2D lane's union crop — spine rule 2.)

**Rule 7 — Blender headless gotchas.**
- Use **absolute** output paths. Relative paths write to CWD, not where you expect.
- `os.makedirs` the output dir first — Blender silently fails otherwise.
- `view_transform = 'Standard'` (Filmic washes game sprites out). `film_transparent = True`, RGBA PNG.
- `bpy.ops.mesh.separate` is a trap on glTF imports — stale edge/face select flags
  re-select everything. Use a bmesh face-centroid split, and `bpy.data.objects.remove()`
  the original or visibility passes resurrect it.
- Meshy rigged exports contain a stray ~42-vertex "Icosphere" placeholder. Filter it by
  name and vert-count before computing the bbox or it wrecks your framing.
- Underside/belly views need a strong underlight **plus** ambient world fill, or you
  render a black silhouette. Two suns is not enough; add a world background node at
  ~0.5 strength.
- Refine output is ~375k faces, above the ~300k rigging limit → remesh to ~100k before rigging.

**Rule 8 — Single-frame azimuth tests are USELESS on animated models.**
Walk-cycle root rotation means one frame lies about the facing. Sweep multiple frames.
On SHORE PATROL the soldiers' walk anim aimed ~70° off body-facing, needing an explicit
`aim_vec` + az290 correction.

**Rule 9 — Verify with a screenshot judged by a DIFFERENT model.**
Do not trust "it looks right to me," and do not trust a subagent's prose claim that it
worked. The loop that works: save the running game's canvas to PNG → spawn an agent on
a different model → have it read the image against explicit acceptance criteria →
PASS/FAIL + defects. This caught two real defects a self-review missed (a stray muzzle
blast at a tank's feet; a muzzle flash too faint to read as the shot origin). Harness:
a tiny HTTP sink that writes POSTed PNGs to `shots/`, plus an injected
`window.saveShot(name)` doing `canvas.toBlob` → `fetch` POST.

**Rule 10 — Size for on-screen size, then render 2–3×.**
SHORE PATROL renders soldiers at 512px and displays them at ~87px — a 6× downscale.
Harmless but wasteful: all fine detail is thrown away, so intricate prompt detail is
wasted effort. Decide the on-screen pixel height first. (Spine rule 3.)

**Rule 11 — Damage/variant states: post-process the PNG, don't re-model.**
The battleship's battle-damaged variant was made by running the clean render through
PIL: desaturate + darken, soot streak gradients, blast-crater radial darkening, warm
ember cores. Seconds, not credits.

---

## Track A vs Track B — the shading style is a choice, and Track B is a recipe

A raw Meshy render reads as *"a 3D render pasted into a pixel-art scene"* —
glossy, smooth-gradient, specular. That is **Track A** (pre-rendered realism, the
DKC/Diablo look) and it is exactly what SHORE PATROL ships — correct there. But a
side-view hero over a flat pixel game needs **Track B**: the render made to read
as pixel art, not as a render. Track B is not a vibe; it is these six steps, the
first three of which are the actual work.

`render_toon_compare.py --mode a|b` renders the SAME model with IDENTICAL camera +
lighting so only the shading differs — always render both and compare before
committing to a look. Side-by-side proof (commando GLB, `references/trackB_vs_trackA.png`):
Track B reads visibly flatter — cel-banded helmet/uniform, hard highlight edge,
dark silhouette outline, quantised palette.

**1. Roughness → 1.0** (mathematically equivalent to Specular = 0). Kills the
glossy tell. In practice Track B bypasses the Principled BSDF entirely and outputs
through an **Emission** node (fully unlit), which is Specular = 0 by construction.

**2. Toon ramp — the strongest tell.** Smooth lighting gradients are the #1
"render" signal; hard bands are the #1 "hand-shaded" signal. Build per material:
`Diffuse BSDF` (a white lighting probe) → **`Shader to RGB`** → `ColorRamp` on
**CONSTANT** interpolation with **2–3 hard bands** → multiply by the model's base
colour/texture → `Emission` → output.
- **`Shader to RGB` is EEVEE-only** (it does not exist in Cycles). Set
  `render.engine = 'BLENDER_EEVEE_NEXT'`.
- Band the *lighting term*, then multiply the base colour in — do NOT band the
  final colour, or every material collapses to 2–3 greys and you lose the model's
  own colours.

**3. Inverted-hull outline.** Duplicate the mesh, push it out with a **negative
Solidify** + flipped normals, flat **dark unlit** (Emission ~0.02) material, and
enable **Backface Culling on the OUTLINE material** (not the model's) so the near
shell is culled and only the far rim pokes past the silhouette. This is robust on
a single fused Meshy mesh, unlike Freestyle. Two gotchas that cost a render each:
- Backface-cull the HULL material, not the model — cull the model and the outward
  shell covers everything and you render a black silhouette.
- Blender's Solidify API: `vertex_group` is the group NAME (str),
  `thickness_vertex_group` is the influence FACTOR (float 0–1) — mixing them up
  throws `expected a float type, not str`.
- **Vary the line thickness** for a hand-drawn read: weight a vertex group by a
  cheap positional noise, map to ~[0.45, 1.0], and set it as the Solidify group.
  A uniform offset reads as CAD; a swelling/thinning line reads as ink.

**Kept from the rules already right — do NOT regress these:**

**4. Orthographic camera; `view_transform = 'Standard'`** (never Filmic/AgX — it
washes sprites out). `film_transparent = True`, RGBA PNG. (Rule 7 already says
Standard; Track B also switches the camera to `type = 'ORTHO'`.)

**5. Render at 2–3× the on-screen size, then LANCZOS down** (Rule 10). Never more
than 3× — the detail is thrown away.

**6. ONE shared palette across ALL frames.** Per-frame quantisation picks
different cluster centres frame to frame and produces visible colour **flicker**.
Build the palette once from all frames pooled, then map each frame to it
(`quantize_shared()` in `render_toon_compare.py`).

Steps 4–6 were already lane rules; **steps 1–3 (roughness→1, toon ramp,
inverted-hull outline) are the gap this section closes** — they are the difference
between a render that sits in the scene and one that belongs in it.

---

## Fail-loud assertions — check these, do not "remember" them

The rules above are the knowledge; these are the gates. Each one names a failure that
has actually shipped. Keep the assertion names stable — tooling cites them.

**`ASSERT_FORWARD_AXIS`** — *confirm the GLB's forward axis before rendering candidates.*
Run the inspect step (mesh count / bbox / longest axis) and record which axis is forward
**before** any candidate montage. Rendering a candidate sweep against an assumed forward
axis burns a full render round-trip and produces a montage where every option is wrong
the same way. If the forward axis cannot be determined from the geometry, render a single
axis-probe still first — do not proceed on a guess.

**`ASSERT_FACING_FROM_RENDER`** — *verify facing from a rendered test still, never from a
filename or a caption.* `enemy_front.png`, a prompt that said "front view", and a Meshy
thumbnail caption are all claims, not evidence. The only acceptable proof that a sprite
faces the direction of travel is a rendered still (or, for animated models, a multi-frame
sweep per Rule 8) looked at against the on-screen motion direction. Never let a name
stand in for the check.

**`ASSERT_MIN_FRAMES`** — *declare a minimum frame count per asset and fail unless the
asset is explicitly marked degraded.* Every animated asset carries a declared minimum
frame count. Producing fewer frames is a hard failure, not a silent shortfall — the only
way to ship under the minimum is an explicit `degraded: true` marking on that asset,
which makes the compromise visible downstream instead of discovering it as jitter in the
running game.

**`ASSERT_SHARED_PALETTE`** — *Track B quantisation must use one shared palette across
all frames.* Per-frame quantisation picks different cluster centres frame to frame and
produces visible colour flicker. Pool all frames, build the palette once, map every frame
to that one palette (`quantize_shared()`), and fail if any frame was quantised
independently. This is the Track B counterpart of Rule 6's shared union bbox.

---

## Costs

~20–40 Meshy credits per model (preview + refine). Check `GET /openapi/v1/balance`.
GLBs are 10–22 MB — gitignore them (`*.glb`), keep only the rendered PNGs in the repo,
and download immediately: Meshy's server copies expire in about three days.

## Do not skip

Rule 1 and Rule 9. Every previous round of rework on SHORE PATROL came from one of them.
