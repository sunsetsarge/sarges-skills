# Tilesets — seams, scoring, Tiled export

`scripts/tileset.py`. Pure Pillow, base interpreter (`C:\AI-Shared\python.exe`).

## The one rule that matters

**Generate at 3x the tile size and keep the center crop.** Everything else on
this page is damage control for having skipped this step.

A framed image — one subject, a vignette, a border, a background that fades —
cannot be made to tile without destroying its edges. The center of a large
continuous surface has none of that, so it is *structurally* close to tiling
before any post-processing runs.

```bash
# generate grass at 96x96 for a 32px tile, then:
python scripts/tileset.py fix grass_96.png --crop-center 32 -o grass.png
```

## Scoring

`seam_diff` = mean L2 RGB distance between wrap-adjacent edges (column 0 vs
column w-1, row 0 vs row h-1) — literally the pixels that sit next to each
other when the tile repeats. 0-255 scale, lower is better.

| Command | Use |
|---|---|
| `tileset.py seam tile.png` | score one tile, exit 1 if it fails |
| `tileset.py sheet sheet.png --tile-size 32 --columns 8` | score every tile, names the worst |
| `tileset.py fix tile.png` | fix it, writes `*_seamless.png` + `*_seam.json` |

**Threshold 12.0 is upstream's number, not a law.** Measured on this skill's
own test tiles: a deliberately non-tiling ramp scored 93.7, a wrapped-noise
texture scored 9.8. The gap between "obviously broken" and "fine" is that
wide, so 12.0 separates the two cases rather than finely grading either.
Re-tune it against your own known-good art before trusting a FAIL.

## Fix strategies

`--strategy auto` (default) escalates and keeps whichever scores lowest —
including the original, so a strategy can never make things worse.

| Strategy | What it does | Cost |
|---|---|---|
| `none` | leave it | — |
| `torus` | roll 50%, feather the center cross, roll back | gentle, preserves content, **often insufficient** |
| `edge_match` | force opposite edges equal by averaging, fade inward | always passes, **overwrites border pixels** |

On the 93.7 test tile: torus only got to 61.5, `edge_match` got to 0.0. That
is the normal shape of it — torus is the polite option and frequently is not
enough.

**Always look at `edge_match` output.** It passes the gate by construction,
so the score tells you nothing about whether it looks right. On a busy tile
it reads as a smeared border. Verify by eye:

```python
# 3x3 montage — seams show up instantly at the tile boundaries
from PIL import Image
t = Image.open("grass.png"); w, h = t.size
m = Image.new("RGBA", (w*3, h*3))
[m.paste(t, (c*w, r*h)) for r in range(3) for c in range(3)]
m.resize((w*3*6, h*3*6), Image.NEAREST).save("montage.png")
```

Or with Lane D, per `references/patterns.md`: `t.shift(w//2, h//2, wrap=True)`
then preview — seams land in the middle where you can see them.

### Palette safety

Blending invents in-between colors, which pixel art must not keep. Every
strategy re-snaps to **the colors already in the input image**. This is a
deliberate divergence from upstream, which snaps to a *named* palette (DB32,
PICO-8…) and so drags the whole pipeline onto fixed palettes. Snapping to the
image's own colors composes with unfake's adaptive per-image palettes (Lanes
A/B/C) and Lane D's presets alike, with neither needing to know about the other.

## Tiled export

`references/export.md` covers Aseprite JSON / Unity / Godot / Phaser — those
are **spritesheet** formats, for animation frames. A tilemap editor needs a
**tileset definition**, which is a different file. Tiled's TSX is the de-facto
standard and Godot/Phaser/LDtk all import it.

```bash
python scripts/tileset.py export overworld.png --tile-size 32 --columns 8 \
    --names grass,dirt,water,stone,path,cliff,sand,snow
```

Writes `overworld.tsx` (the tileset, with per-tile `name` properties) and
`overworld.tmj` (a 10x10 demo map, so you can confirm it renders without
authoring anything in Tiled).

- `--animate-frames N` declares tiles `0..N-1` as an animation on tile 0 —
  animated water, torches.
- Grid dims are validated against the actual image before anything is
  written. Tiled renders garbage rather than erroring on a mismatch, so this
  refuses instead.
- **TMJ layer data is firstgid-offset**: the first tile is `1`, not `0`.
  Writing `0` means "empty" and gives you a blank map.

## Where this gets used

Wilmington 16-Bit (walkable downtown) and skill-snes-rpg (tile overworlds,
towns, dungeons) both need tilemaps, and both consume TSX directly.
