# QC methodology

`scripts/qc_check.py` never eyeballs a result — every check is a programmatic
re-analysis of the pixelize.py output, run from the venv-unfake interpreter (it needs
`unfake` + `numpy` + `PIL`).

## The four checks

1. **True-grid.** Re-run unfake's own scale detector (`runs_based_detect`) on the
   `*_grid.png` (the native, pre-upscale resolution). It must report scale `1` —
   meaning the image is already at its true pixel-art resolution and can't be
   downscaled further. This is the core claim of "true-grid pixel art" made
   verifiable instead of asserted.

   **Why `runs_based_detect` alone, not both detectors:** an earlier version of
   this check required `edge_aware_detect` to also report `1`, on the theory that
   two independent detectors agreeing is a stronger guarantee. Two real cases
   changed that:
   - Phase 0 hit a case (ChatGPT/Lane C output) where a single unfake pass left
     `runs_based_detect` reporting 1 while `edge_aware_detect` still found a
     genuine residual 5x block pattern — re-running unfake on its own output
     correctly collapsed it, and both agreed on 1 afterward. This is why
     `converge_grid()` still iterates (up to 3 passes).
   - Phase 1's own acceptance test then hit the opposite case: a manually-verified
     correct 65×65 sprite (large uniform flat-color background, small character)
     where `edge_aware_detect` returned a false `18` and iterating unfake further
     did **not** fix it — because there was nothing wrong to fix. The image was
     already correct; the detector was just fooled by the flat region. Requiring
     both agree would have permanently failed a genuinely good result and sent
     `converge_grid()` into a pointless collapse/restore loop each iteration (see
     `run_unfake_safe()`).

   Net effect: `runs_based_detect` has been reliable in every case observed so
   far (correctly finds both "needs more downscaling" and "already at native
   resolution"), while `edge_aware_detect` has a known false-positive mode on
   flat-dominant backgrounds. So it's the authoritative signal; `edge_aware_detect`
   is still reported in the JSON for transparency (and used as the *trigger* for
   `converge_grid()`'s extra passes, since it correctly catches real residual
   patterns) but no longer gates pass/fail on its own. If you ever see `qc_check.py`
   fail `true_grid` on a file that went through `pixelize.py`, `runs_based_scale`
   itself was non-1 — that's a real problem, not a detector quirk.

2. **Color count.** `unfake.count_colors()` on the grid image must be `<= max-colors`
   (default 32, matches `pixelize.py --colors`). Straightforward — this just confirms
   the Wu quantization pass actually landed at or under the requested budget.

3. **Clean alpha.** If the grid image has an alpha channel, every pixel's alpha value
   must be exactly `0` or `255` — no partial/anti-aliased transparency. Soft alpha
   edges are the most common way a "pixel art" image quietly isn't: it can pass every
   other check and still look wrong in an engine that doesn't premultiply alpha
   correctly. Images with no alpha channel (fully opaque) pass this trivially.

4. **Crisp upscale.** Verifies `*_final.png` is an *exact* integer nearest-neighbor
   upscale of `*_grid.png` — every `scale × scale` block in the final image is a
   single solid color, and those colors match the grid image pixel-for-pixel. This is
   what "crisp and openable at 400% zoom" means when verified instead of eyeballed:
   a viewer's own smoothing/resampling can't have snuck in anywhere in the pipeline.

## Reading `qc_check.py` output

Each run writes a `<name>_qc.json` report next to the grid file (same schema as the
printed summary) and exits `0` on pass / `1` on fail — safe to gate a script on the
exit code. A `FAIL` on `true_grid` specifically is usually a source-image problem
(too much residual anti-aliasing for unfake to resolve in 3 passes), not a bug in the
QC script itself — try a different `--method` or bump `--colors` down before assuming
QC is wrong.

## Known upstream issues (don't waste time rediscovering these)

- **`pixeloe` PyPI package (v0.1.4) has broken packaging.** Its own console-script
  entry point (`pixeloe.pixelize.exe`) fails immediately with
  `ModuleNotFoundError: No module named 'pixeloe.cli'` — don't use it.
  `pixeloe.torch.pixelize` also needs `torchvision` and `tqdm`, neither of which are
  declared as dependencies — both are installed manually into `venv-pixeloe` (see
  the venv setup, not a `requirements.txt`, because the package's own metadata can't
  be trusted). `pixeloe_worker.py` drives the `pixelize()` function directly instead
  of the CLI. Its `pixel_size` parameter is a **downscale factor**, not a target
  resolution — `pixeloe_worker.py` computes it from `min(width, height) // target_size`.
- **A single unfake pass may not converge.** See the true-grid check above —
  `pixelize.py` handles this, but if you're calling unfake directly (bypassing
  `pixelize.py`) for debugging, don't assume one pass is enough.
