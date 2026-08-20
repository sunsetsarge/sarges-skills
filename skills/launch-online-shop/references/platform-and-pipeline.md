# Platform & Product Pipeline

Depth for Phases 1, 3, and 5. Reference implementations: `scripts/README.md`.

## 1. Accounts & fulfillment wiring (owner does the human bits)

The owner must do (you cannot — their login/money/identity):
1. **Sales channel account** — Etsy seller (bank + card + tax/identity) or Shopify plan.
2. **Printify account**, then **Manage stores → Add store → [channel] → authorize (OAuth)**.
3. Confirm in the connection: **shipping profiles pulled**, and the **production-partner /
   POD disclosure ON** (Etsy *requires* disclosing the print partner).
4. Ping you "connected" — then you script everything downstream off the Printify API token.

**Costs to set expectations:** Etsy $0.20/listing (renews per sale / 4 months) + 6.5% txn +
~3%+$0.25 processing. Shopify monthly plan + processing. Printify bills the production cost per
order; the owner never touches fulfillment.

**Connecting a second channel makes a second Printify store** — products are per-store, so
selling the same catalog on Etsy *and* Shopify means a scripted **recreate** per store, not a
manual rebuild. Reuse the same uploaded artwork image-ids.

## 2. Secrets

Never hardcode tokens. Load via a config module (env → keyring → file), e.g. Saspan's
`saspan_config.py` exposing `auth_headers()`, `BASE`, `SHOP_ID`, `printify_pat()`. New shop =
new loader with the same shape.

## 3. Creating products via the Printify API

Core call: `POST /v1/shops/{shop}/products.json` with:
- `blueprint_id` (e.g. 12 = Bella+Canvas 3001 tee, 937 = canvas, 400 = kiss-cut sticker),
- `print_provider_id`,
- `variants` (enabled ids + prices),
- `print_areas`: `[{variant_ids, placeholders:[{position, images:[{id,x,y,scale,angle,flipX,flipY}]}]}]`.

**Clone, don't rebuild.** To copy an approved product into a new store/channel, GET the source,
reuse each placeholder's image-id and geometry, drop product-specific placeholders (neck), and
POST to the new shop. (Saspan `create_etsy_batch.py` does exactly this.)

## 4. Print-area geometry (where designs get "cut off")

`x`,`y` are the image *center* in the print area (0–1); `scale` is fractional width.
- `x=0.5, y=0.5, scale=1.0` = centered, full print width.
- **Tall designs clip at `scale=1.0`** (top/bottom run past the printable area) → shrink to
  `scale≈0.80` and center (`y=0.5`) so the whole thing shows with even margins.
- A design sitting *high* (`y≈0.41`) is top-heavy and can look cut off even when nothing is
  clipped — center it.
- **Verify each design visually** (download the regenerated back mockup). Aspect ratios vary:
  wide/short ads may be deliberately scaled *up* (1.1–1.14) — never blanket-overwrite tuned
  placements. Only re-center the ones at the broken default. (Saspan `recenter_back_prints.py`
  targets only the `y≈0.412 & scale≈1.0` signature and preserves custom layouts.)
- **Dark vs light shirts use different artwork** (white-ink inversion for darks). The same
  x/y/scale does *not* translate between them — tune separately.

## 5. Mockups & QA

- After any `print_areas` update Printify **regenerates mockups asynchronously** — refetch to get
  fresh URLs; a live product may briefly have no `back` image.
- **Finding the back mockup:** Etsy images carry `position:"back"`; Shopify images carry
  `position:"other"` with `camera_label=back-2` in the `src`. Select on the
  **`camera_label=back` substring** to catch both.
- **Stickers/blueprint 400 don't auto-generate mockups** → render your own product photos
  (rounded corners + shadow on white) and wire them into the review gallery via `file:///` paths.
- **QA every mockup**: does it show the design, on the right side, fully in frame? Build a
  contact-sheet to eyeball a batch at once instead of one-by-one.

## 6. API gotchas (failures you WILL hit)

| Symptom | Cause | Fix |
|---|---|---|
| `8253` "cannot swap images on existing product" | Printify won't change artwork in place | **delete + recreate** the product |
| `8253` "Provided images do not exist" on update | a placeholder (usually **neck**) holds a **deleted** image id | send only `back`/`front` placeholders; drop orphans |
| Update `400` "field required: placeholders.N.images" | you sent an **empty** placeholder | skip placeholders with no images |
| Persistent `500` on any update (even title no-op) | Printify per-product server lock | retry later; not your payload |
| Product shows live but you can't find it via id | ids rotate on recreate; the old id 404s | list the shop and match by title/`external` |
| "Is it published?" ambiguous | `is_locked`/`visible` are unreliable | trust the **`external`** field |

Rate-limit bulk writes (~1–1.5s between products). Track a manifest so reruns are idempotent.
