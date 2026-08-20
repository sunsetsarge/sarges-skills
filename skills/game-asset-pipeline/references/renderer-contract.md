# Renderer contract — manifest shape and Canvas-2D rules

Read before writing draw code. The packing decisions upstream only pay off if the
renderer honours them, and several of the rules below are non-obvious enough that
they cost real debugging time to find.

## Manifest shape

`sync_assets.py` emits this. Adapt names freely; keep the *properties*.

```json
{
  "version": 1,
  "reference": { "w": 390, "h": 844 },
  "sprites": {
    "hero_dusk": {
      "file": "sprites/hero_dusk.webp",
      "cellW": 157, "cellH": 124, "cols": 8, "rowCount": 5,
      "drawScale": 0.742, "displayH": 92, "mirrored": false,
      "anims": { "run": { "row": 0, "frames": 4, "fps": 14 } }
    }
  },
  "unusable": { "enemy_yeti": "row1 frames fuse two creatures" }
}
```

- **`drawScale`** converts encoded pixels to on-screen size. It exists because the
  packer never upscales: encode height is `min(native, displayH*2)`, so the renderer
  scales *down* by this factor. Multiply it by any per-instance scale.
- **Cells are bottom-anchored.** Draw so the cell's bottom edge sits on the ground
  line. Ground alignment is a property of the atlas; do not compute anchors at
  draw time.
- **`mirrored`** is informational. Facing is already baked — never flip at runtime.

## Frame selection must be pure

```js
function frameAt(anim, elapsed, loop = true) {
  if (anim.frames <= 1) return 0;
  const i = Math.floor(elapsed * anim.fps);
  return loop ? ((i % anim.frames) + anim.frames) % anim.frames
              : Math.min(anim.frames - 1, Math.max(0, i));
}
```

A pure function of `(animation, elapsed)` means headless and deterministic runs need
no renderer at all, and a replay reproduces exactly. Do not advance frame counters
from inside the render loop.

## Drawing

```js
const s = meta.drawScale * scale;
const w = meta.cellW * s, h = meta.cellH * s;
ctx.drawImage(img, frame * meta.cellW, anim.row * meta.cellH, meta.cellW, meta.cellH,
              x - w / 2, groundY - h, w, h);
```

Keep a fast path for the common case (upright, opaque, no rotation). `save()`/
`restore()` on every entity every frame is measurable at 40+ sprites.

## Canvas rules that cost real time to discover

**A dark character on a dark background disappears.** Give it a rim light:

```js
ctx.shadowColor = identityColour; ctx.shadowBlur = 14;
drawSprite(...);            // wide glow
ctx.shadowBlur = 6; drawSprite(...);   // tighter edge
```

The shadow hugs the sprite's alpha, so this is a real outline of the pose rather than
a blob behind it. On the reference project a black terrier on night ground was
genuinely invisible until this went in.

**`source-atop` cannot tint a sprite.** It composites against the *entire canvas*, not
against the sprite you just drew, and paints hard-edged rectangles across the scene.
For hit flashes and status tints, redraw the same sprite additively (`lighter`) and use
a coloured `shadowColor` for the edge.

**Canvas `multiply` is not linear in alpha.** The result is
`src * ((1-a) + a*tint/255)`. A mid-tone tint at alpha 0.5 barely darkens anything —
a first attempt at a night grade using `#2b3f7a` at 0.52 still read as a sunny
afternoon. Compute against your brightest source pixel and check the number, or tune
against a screenshot.

**AI "parallax layers" are usually opaque full-bleed bands, not alpha layers.** Sky /
Far / Near / Ground come back as four complete opaque images. Draw them back-to-front
as horizontal bands, each covering the bottom of the one behind. Two consequences:

- **Feather each band's top edge** into the band behind it, or you get a hard
  horizontal cut straight through the artwork (a tree canopy sliced by a straight
  line). Build the feathered copy once and cache it; do not do it per frame.
- **Mirror alternate tiles.** The art is rarely seamless, and mirroring every other
  copy makes the join match by construction.

**Cap simultaneous sprites and particles for legibility, not just performance.** Past
roughly 40 sprites and 400 particles a portrait screen stops being readable regardless
of frame rate. Element rims and telegraphs should always draw above other VFX.
