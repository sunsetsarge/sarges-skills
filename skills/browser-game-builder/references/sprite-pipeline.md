# Directional Sprite Pipeline (full detail)

Everything about getting 8-direction sprites from an image generator into a
top-down game correctly. The scripts in `../scripts/` implement this; this file
is the theory so you can debug when a sheet misbehaves.

## Contents
1. Why 8 directions
2. The engine side: loading + picking a facing
3. Generating sheets
4. Slicing
5. The facing bug and its two remaps (the important part)
6. QC rubric
7. Animation hooks (pointer)

## 1. Why 8 directions
A top-down / 3-4 view sprite has baked-in perspective and lighting; rotating it
in code looks broken (a tank's top rotates but its shadow/treads don't). So
pre-render N facings and pick the nearest to the unit's heading. N=8 is the sweet
spot: smooth enough, cheap to generate. N=16 for hero units if you want.

## 2. Engine side
Files: `assets/<key>_0.png … _7.png`. Convention: **frame 0 = East, then
clockwise** (`0=E,1=SE,2=S,3=SW,4=W,5=NW,6=N,7=NE`) because canvas +y points down,
so increasing screen angle is clockwise.

```js
const TAU = Math.PI*2;
// heading (radians, 0=East, clockwise) -> frame index
function dirIndex(face, n){ const i = Math.round(face/(TAU/n)); return ((i%n)+n)%n; }

const SPRITES = {};
function loadDirSprites(key, base, n=8, size=32){
  const set = {img:new Array(n), ready:0, n, size}; SPRITES[key]=set;
  for(let i=0;i<n;i++){ const im=new Image();
    im.onload = ()=>set.ready++;
    im.onerror= ()=>{ if(SPRITES[key]===set) delete SPRITES[key]; }; // -> vector fallback
    im.src = `${base}_${i}.png`; set.img[i]=im; }
}
// draw: const im = spr.img[dirIndex(u.face, spr.n)];  // no rotation, ever
```
Deleting the set on error is what lets the game run before art exists — the draw
code checks `if (spr && spr.ready>=spr.n) …drawImage… else …vector fallback…`.

## 3. Generating sheets
Prompt an image model for: *"8 directions of \<unit\>, top-down 3/4 view, arranged
in a 3×3 grid with the center empty, consistent camera angle, plain white
background, no shadows on the ground."* One unit per sheet. Keep the camera angle
identical across every unit or they won't sit together in-game. Sources that work:
ComfyUI (local, free, scriptable — best for batches), Stability API, DALL·E /
ChatGPT desktop. Whatever the source, the output is a white-background grid.

## 4. Slicing
`slice_sprites.py` does: soft white-key → cut 9 cells → map the 8 outer cells to
compass indices (`CELL2DIR`) → trim each to its alpha bbox → scale all 8 by ONE
common factor (so relative proportions hold) → save tight PNGs.

The soft white key (not a hard threshold) matters: a hard `>240 = transparent`
eats light-grey unit pixels and leaves white halos. The soft key keys pixels that
are *both* bright *and* low-saturation:
```
light = clip((max_rgb-200)/55)      # brightness
flat  = clip((28-(max-min))/28)     # greyness
alpha *= 1 - light*flat             # white-ish -> transparent, coloured stays
```

`CELL2DIR` is the generator's grid layout, and it is the thing most likely to be
"wrong" — which is fine, because you fix layout errors with a remap after
verifying, not by guessing the map. The bundled default is the natural compass
(top row NW/N/NE, etc.).

## 5. The facing bug — READ THIS
**Every AI sprite sheet must be facing-verified before shipping.** Generators are
not consistent about which way the figure faces in each cell. Symptom in-game:
units slide backwards or crab sideways. Run `verify_facing.py <key> --frames 0-7`
and look at the barrel/nose/gun:

- **Frame 0 must point East (right).**
- **Frame 6 must point North (up).**

If it's wrong it's almost always one of two whole-set transforms. Model the
observed facing as an angle per frame and match the pattern:

| Observed | Meaning | Fix | Reindex |
|---|---|---|---|
| frame0 faces West, 2=N, 4=E, 6=S (all reversed) | **180° rotation** | `--flip` | `new[i]=old[(i+4) mod 8]` |
| frame0 West & frame4 East swapped, but 2=S and 6=N look **right** | **horizontal mirror** | `--mirror` | `new[i]=old[(4-i) mod 8]` |

Why the mirror is a trap: because N/S frames look correct, people "fix" it with a
+4 rotation, which then breaks N/S. Check frames 2 and 6 specifically — if they're
already right, it's the mirror, not the rotation.

Both remaps are **self-inverse** (apply twice = identity), so trying one is safe:
if it looks worse, apply the same flag again to undo. Derivation of the mirror
case: if a sheet's frame `i` actually shows heading `180° − 45i` (a reflection),
then to make frame `i` show `45i` you pull from old index `4−i`.

Re-slice from the source sheet with the right flag rather than hand-editing files.

## 6. QC rubric (is this sprite shippable?)
Montage each unit's frame 0 beside a label of what it should be, and check:
- **Silhouette reads as the unit type** at game scale (a tank looks like a tank,
  not a blob). This is the one that catches "generative bizarreness" — e.g. a
  bulldozer that rendered as a featureless capsule.
- **Faces East in frame 0** (section 5).
- **Transparent background**, no white halo.
- **Scale is sane** relative to siblings (a scout isn't bigger than a heavy tank).
- **Lighting/angle consistent** with the rest of the roster.
A vision-capable model can grade this directly from the montage. Regenerate the
failures — don't ship art you'd be embarrassed to sell. Infantry are the usual
weak point (too small/symmetric to read); accept them at scale or regenerate with
a clearer top-down pose.

## 7. Animation
Static frames feel dead; add code motion (recoil, leg-swing, rotors, dust). See
`game-architecture.md` → Animation.
