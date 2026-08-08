# Third-party code in this skill

## ianlintner/ai-pixel-art-image-generation (tilesets + art QC)

<https://github.com/ianlintner/ai-pixel-art-image-generation>, MIT licensed.
Evaluated 2026-08-08 at `main`; ~900 of its 4,708 lines were worth taking.

| Taken | Became | Ported from |
|---|---|---|
| seam metric + tiling strategies | `scripts/tileset.py` | `scripts/lib/seamless.py` |
| Tiled TSX/TMJ writers | `scripts/tileset.py` | `scripts/export_tiled.py` |
| art + frame-consistency metrics | `scripts/art_qc.py` | `scripts/lib/qa_metrics.py` |

Rewritten rather than vendored, for three reasons:

1. **Palette coupling.** Upstream re-quantizes against a *named* palette
   (DB32, PICO-8…), which forces the whole pipeline onto fixed palettes.
   Both ports snap to the colors already in the input image instead, so they
   compose with unfake's adaptive per-image palettes (Lanes A/B/C) and Lane
   D's presets without either side knowing about the other.
2. **`palette_fidelity` dropped.** Upstream hard-fails anything not 100% on
   a named palette — meaningless against adaptive palettes.
   `outline_coverage` demoted to soft: outline-free styles are legitimate.
3. **Precondition warning added.** Upstream reports silhouette metrics with
   no caveat; they are only meaningful on character-isolated frames. See
   `opaque_fraction` in `art_qc.py` and the writeup in `references/art-qc.md`.

**Not taken:** every provider client (`openai_client`, `azure_client`,
`gemini_client`, `fal_client`, `batch_client`, ~950 lines) — all paid-API
generation, where this skill uses local ComfyUI and Lane D. Also skipped
upstream's `pixelize.py` (plain nearest-neighbour + PIL quantize, strictly
weaker than this skill's pixeloe→unfake chain), its palette and outline
libraries (Lane D already covers both), and its `POSE_LIBRARY`
(`references/animation.md` has a more specific walk-cycle spec).

Thresholds in both scripts are upstream's starting values, from a repo with
no external validation. They were checked against purpose-built controls and
this skill's own evals (see `references/art-qc.md` and `tilesets.md`) and
behaved correctly, but re-tune before treating a FAIL as authoritative.

### License

MIT, Copyright (c) 2026 Ian Lintner. Full text:
<https://github.com/ianlintner/ai-pixel-art-image-generation/blob/main/LICENSE>

## Gamezxz/pixel-art-studio (Lane D)

Lane D — the deterministic Pillow drawing engine — is imported from
<https://github.com/Gamezxz/pixel-art-studio>, MIT licensed.

- Imported at commit `f8c246635c4621a6c2b427833149afdc3dc3c719` on 2026-08-08.
- Verified running unmodified on Windows with `C:\AI-Shared\python.exe`
  (Pillow 10.4.0). Only Pillow is required — no torch, unlike Lane A/B's
  `venv-pixeloe`.

### Files taken verbatim

| File | Notes |
|---|---|
| `scripts/pixelstudio.py` | The drawing/animation/export library (1386 lines) |
| `scripts/lpc.py` | LPC universal-spritesheet layout adapter |
| `scripts/study.py` | Extracts palette/technique data from a reference image |
| `scripts/pixelpipe.py` | Cleanup CLI that emits a regenerable `build.py` |
| `references/patterns.md` | Proportions, sizes, silhouette-first order |
| `references/techniques.md` | Ramps, shading, dithering, AA, outlines |
| `references/palettes.md` | Palette budgets and presets |
| `references/animation.md` | Frame counts, timing, puppeting, pivots |
| `references/lpc.md` | LPC sheet conventions |
| `references/export.md` | Engine export formats |
| `references/cleanup.md` | Hybrid generated-art cleanup playbook |
| `references/sharp_edges.md` | Known failure modes |
| `references/validations.md` | Per-iteration critique checklist |
| `references/learned/` | Upstream's studied-style cards |

### Local modifications

- `references/cleanup.md`, `references/palettes.md`: `python3` invocations
  rewritten to `C:\AI-Shared\python.exe` and POSIX paths to Windows paths.
  Code is otherwise untouched.

**No LPC art assets are included.** `lpc.py` implements only the grid
convention. Actual Liberated Pixel Cup *artwork* is CC-BY-SA 3.0 / GPL 3.0 and
carries per-artist credit requirements — none of it ships here, and none of it
should be imported into a Saspan Salt / Local Lore product without checking
those terms.

### License

```
MIT License

Copyright (c) 2026 Gamezxz

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
