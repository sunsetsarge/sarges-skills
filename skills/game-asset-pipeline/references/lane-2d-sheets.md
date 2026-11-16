# Lane 2D — AI grid sheets → sprite atlas

For art that arrives as a grid of poses on a solid near-white background: ChatGPT,
DALL-E, Midjourney, or any "make me a sprite sheet" generation.

Two stages. Stage A cuts frames out of the sheet; Stage B packs frames into an
engine-ready atlas. If you already have trimmed frames, skip to Stage B.

---

## Stage A — sheet → frames (`scripts/lane-2d/slice_sheet.py`)

Detects the matte colour, builds a foreground mask, finds row bands by projection,
clusters frames within a band, strips baked caption text, and writes
`sliced/<name>/r<row>_f<frame>.png` plus a `meta.json` of boxes.

Modes: `grid` for uniform clean sheets, `gaps` for irregular spacing (projection
bands), `auto` to guess. Per-sheet params worth tuning: `thresh` (matte tolerance),
`min_px` (minimum component size), `gap` / `band_gap` (separation), `label_reject`.

## Read the SOURCE sheet's own structure first

Open the original sheet, at a readable size, before you slice or judge anything. These
sheets usually label themselves, and the labels tell you the layout:

- **Row-labelled** (`IDLE` / `WALK LEFT` / `ATTACK` down the left margin): rows are
  animations, columns are frames. The common, easy case.
- **Column-labelled with direction headers** (`DOWN` / `DOWN-LEFT` / `LEFT` / `UP` …
  across the top): columns are **facings**, and the animation runs **vertically** in
  bands down each column. To get a left-facing walk you take the LEFT column's WALK
  band — not a row.
- **Transposed** (directions down the left, animation blocks across the top): the same
  thing the other way round.

Get this axis wrong and a directional sheet looks exactly like a useless turntable:
measuring frame widths *across* a row of an 8-direction sheet gives wild variation,
because you are measuring different facings, not different frames. That misreading
cost a real project two enemies and a boss.

A left-margin label column is also the classic reason blob-detection slicing fails —
the detector merges the label text into the first cell and every downstream box is
wrong. If the sheet is a clean uniform grid, slice with **fixed cell coordinates**
(rows × cols computed from the sheet dimensions) rather than blob detection.

**Before you accept a slice, classify every row.** Three things masquerade as
animations:

- **Camera turntables.** Columns are viewing angles, not time. Playing the row spins
  the creature. Extremely common in AI sheets. Symptom: frame widths swing wildly
  (46–115px) while heights stay pinned, and the subject rotates across the row.
- **Caption strips.** A band containing only baked text ("WALK LEFT"). Symptom: a
  1-frame row far shorter than the character's median height.
- **Fused slices.** Two poses merged into one frame because the gutter was too tight.
  Symptom: a frame 2–5× the median width.

Run `contact_row.py <out.png> <cell> <name>:<row>` on anything suspicious and **look
at it**. Frame counts never prove a row is correct.

If a row is a turntable, either pick one usable angle and rely on procedural motion
in the engine (bob, sway, squash — code-driven animation reads fine at speed), or log
the sheet for regeneration. Do not ship a spinning walk cycle.

## Determining facing — do this from evidence, every time

Never inherit a facing table from another project. On the reference project the
inherited table was wrong in *both* directions, and a wrong entry means a character
runs backwards.

1. `audit_facing.py` → one labelled crop per character → **read the image**.
2. For anything ambiguous, `zoom_check.py` → 3 frames of that row at high zoom with a
   centre line drawn → read it again.
3. Record the true source facing per character in the job spec.

Watch for the trap: one real sheet has "WALK LEFT" baked into the artwork while the
character faces right. Captions lie.

---

## Stage B — frames → atlas (`scripts/lane-2d/sync_assets.py`)

```bash
C:\AI-Shared\python.exe sync_assets.py --root ART_ROOT --jobs asset_jobs.json \
    --out public/assets --ref 390x844 --contact
```

Emits one WebP grid per character (row = animation, column = frame) plus
`manifest.json`. One file per character keeps the request count at ~20 instead of
~130, and WebP compresses the transparent padding to almost nothing.

### The job spec

Authored data, not auto-detection. Per character: which row is which animation, the
**source** facing, and the intended on-screen height.

```json
{
  "heroes": {
    "hero_dusk": {
      "facing": "right", "displayH": 92,
      "anims": { "run": {"row": 1}, "attack": {"row": 2},
                 "idle": {"row": 5}, "hurt": {"row": 6} }
    }
  },
  "enemies": {
    "enemy_orc_axeman": {
      "facing": "right", "displayH": 88,
      "anims": { "walk": {"row": 1, "drop": [0]}, "attack": {"row": 2} }
    },
    "enemy_brute": {
      "facing": "left", "displayH": 108, "degraded": "turntable",
      "anims": { "walk": {"row": 2, "take": [2, 3]} }
    }
  },
  "_unusable": { "enemy_yeti": "row1 frames fuse two creatures; unusable" }
}
```

- `facing` — what the SOURCE art does. The packer mirrors so heroes end up facing one
  way and enemies the other. `"frontal"` is never mirrored.
- `drop: [i]` — remove specific frames (a baked caption at index 0 is common).
- `take: [a, b]` — keep an inclusive window; how you extract one coherent stretch out
  of a turntable.
- `displayH` — on-screen height at your reference resolution. Drives everything.

Group keys (`heroes` / `enemies` / `bosses` / `props`) set the desired facing per
group; adapt them to the project.

### What the packer does, and why

**Union-box crop per animation.** Every frame of an animation is cropped to that
animation's union alpha box, never its own. See spine rule 2 — this is the jitter fix.

**One scale per character**, taken from a reference row (run/walk) and applied to every
animation. Never scale a frame by its own bbox; that made dying enemies balloon on the
reference project.

**Never upscale**: `enc_h = min(native_median_h, displayH * 2)`, then
`drawScale = displayH / enc_h` goes in the manifest and the renderer scales down.

**Bottom-centre in a uniform cell.** Ground alignment becomes a property of the atlas
and the renderer never computes an anchor.

**Outlier rejection against a character-wide median**, not a per-row one. A row can be
mostly fused or hold only two poses, and then the row median *is* the outlier. Frames
wider than ~1.75× or shorter than ~0.45× the character median are dropped, then the
union box itself is guarded — one surviving fused frame stretches the box and shrinks
the artwork to a speck inside a giant cell. That bug shipped once and produced 955px
and 1486px cells.

**Defringe.** Partial-alpha pixels are un-premultiplied against the white matte:
observed edge colour is `a*C + (1-a)*255`, so recover `C`. This is the difference
between "the artwork's own outline" and "a white halo", and it is where perceived
quality is decided. Fully opaque pixels are untouched, so a genuine white stroke in
the art survives.

**WebP at quality ≥ 80.** Below ~70 the alpha edge blocks up into a visible rectangle
that reads as an opaque background.

### Then look at it

`qa_packed.py <out.png> <zoom> <key>:<anim> …` renders the **packed** output on a dark
checkerboard with a ground line drawn. Halos, clipped edges and baseline drift are
only judgeable here, at size, after packing — not from the source sheet.

## Stage B-alt — frames → Aseprite source + sheet + JSON (`scripts/lane-2d/ase_pack.py`)

Use this instead of `sync_assets.py` when the engine reads Aseprite's JSON (Godot,
Phaser, Unity importers), when animations need names, loop direction and timing as
data, or when the art should stay editable in Aseprite afterwards. It needs Aseprite
installed (Steam build found automatically) and runs it headless.

The input must already be equal-size frames, so run `cut_cells.py --format png` first:

```
python cut_cells.py sheet.png cells/ --name knight --rows 3 --cols 3 --anchor bottom --format png
python ase_pack.py out/ --name knight --frames "cells/knight_[0-9]*.png" \
    --tags "turn:1-8" --fps 6 --max-colors 16 --pivot bottom-center
```

That writes `knight.aseprite` (tags, timing, locked palette), `knight.png` (RGBA
sheet) and `knight.json` (frames, `meta.frameTags`, `meta.slices`). A clean
equal-cell sheet can go straight in with `--sheet PNG --cell WxH --row-tags a,b,c`.

Rules it enforces, each learned the hard way:

- **Frames of different sizes are an error**, never padded. Padding moves the anchor.
- **Palette lock keeps transparency.** Soft alpha is made binary first, index 0 is a
  spare transparent entry, and the opaque-pixel count is compared before and after.
- **No per-frame trim by default.** `--trim` is opt-in and the engine must then apply
  `spriteSourceSize`, or the walk cycle jitters (spine rule 2).
- **Generator halos come off with `--defringe`.** PixelLab drew a ragged white fringe on
  10 of 14 frames of a black terrier (2026-11-15). `--defringe [N]` removes light pixels
  (min channel above N, default 180) that connect to transparency and keeps enclosed ones
  such as eye glints. Opt-in: art with a genuinely light outline would lose it. Write the
  flag after `OUT_DIR`, or give it a number, so it does not swallow the folder name.
- **It never touches the real Aseprite settings.** Each run uses a throwaway config
  folder (`ASEPRITE_USER_FOLDER`).

The glob matters: `cells/knight_*.png` would also pick up `knight_contact.png`.
`python ase_pack_selftest.py` re-checks the tool after an Aseprite update.
