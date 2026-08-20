# Scripts

## In this skill (portable)

- **`tm_gate.py`** — the fail-closed trademark pre-publish gate (Phase 2). Stdlib-only, no config.
  `python tm_gate.py "Brand A" "Brand B" [--file brands.txt] [--probe] [--confirmed] [--out r.json]`
  Exit 0 only if every brand is GREEN. See `../references/trademark-vetting.md`.

## Reference implementations to adapt (from the Saspan Salt build)

These live in `C:\Claude\Scripts` and are **Saspan-specific templates** — copy and adapt for a new
shop (new secrets loader, new shop ids, new design set). They are the working proof of the pipeline
described in `../references/platform-and-pipeline.md`.

| Script | What it does | Adapt for a new shop |
|---|---|---|
| `saspan_config.py` | secrets loader (env → keyring → file); `auth_headers()`, `BASE`, `SHOP_ID` | rewrite with your token source; keep the same shape |
| `create_products_base.py` / `create_light_and_canvas.py` / `create_dark_shirts.py` | create products via Printify API (blueprint/provider/variants/geometry) | new blueprints, providers, artwork ids |
| `create_etsy_batch.py` | **clone** approved products into a second (Etsy) store, reusing image-ids + geometry, dropping the neck placeholder | change source/target shop ids + the curated design list |
| `recenter_back_prints.py` | fix back-print geometry, targeting ONLY the broken `y≈0.412 & scale≈1.0` default and preserving hand-tuned layouts; dry-run first | reuse as-is against your shop ids |
| `build_review_gallery.py` | build the approve-to-publish HTML gallery (incl. `file:///` sticker photos) | repoint shop id + photo dir |
| `publish_approved.py` | flip only owner-approved products live | reuse |
| `create_stickers.py` / `brand_stickers.py` / `make_sticker_photos.py` | kiss-cut sticker products + branded footer + own product photos (blueprint 400 has no auto mockups) | reuse the photo-generation pattern |

**Gotchas** these encode are summarized in `../SKILL.md` (error 8253 delete+recreate, orphaned neck
placeholder, `external`=published truth, camera_label=back matching, per-product 500 locks). Read
those before running anything against a live shop.

> Do not hardcode tokens in any adapted copy — always go through a config loader.
