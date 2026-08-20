# Launch, Review Gate & Marketing (Phases 5–7 + service add-on)

## The review/approval gate (before anything goes live)

Publishing is outward-facing and owner-visible — **never mass-publish unreviewed.** Build a
**review gallery**: one card per design showing the actual mockups (front/back/variants), price
range, live/draft status, and a "publish" checkbox. The owner ticks keepers → export the approved
list → a publish step flips only those live. (Saspan `build_review_gallery.py` +
`publish_approved.py`.) For stickers or anything without Printify mockups, wire in your own product
photos via `file:///` paths so the gallery isn't blank.

Also build a quick **contact-sheet** (tiled thumbnails) for any batch operation so the owner can
eyeball 60 designs at once instead of one screenshot at a time.

## Launch = demand-first, not build-first

Re-state the honest frame: **live ≠ earning.** New shops get a small visibility bump, then ranking
depends on clicks / favorites / sales. The first 1–3 sales are the hard ones; they bootstrap the
flywheel.

**Marketing order (for a local / nostalgia / niche brand):**
1. **Organic-first** — post where the actual audience already gathers (relevant FB groups, local
   community pages, niche subreddits). Give value / show the piece; don't just drop links.
2. **Geo-targeted Meta** — a *tiny* budget ($1–3/day) aimed at the specific town/region/interest.
3. **Skip** cold national Google and broad national FB early — you'll burn money with no ranking
   to catch it.
4. Platform ads (Etsy Ads) only to nudge the **first** sales that start the ranking flywheel.

Validate a niche on free channels (FB groups, a poll, a small pre-launch post) **before** scaling
designs. Then **measure which themes convert** and expand only the winners past the demand
governor (e.g., ≥10 organic sales before the next bulk batch).

## Launch kit contents (reusable)

- A short "why this exists" brand story (no source-archive talk).
- 3–5 hero images / mockups per flagship design.
- SEO-tuned titles + 13 tags + descriptions (see `copy-pricing-seo.md`).
- A geo-Meta + organic-post plan with the exact groups/pages to post in.
- A first-week checklist (post cadence, respond to comments, ask early buyers for reviews).

## Service add-on (often earns before products do)

A **service** attached to the same brand can out-earn low-traffic product sales early, with near-zero
inventory. Pattern (from Saspan's photo-restoration offering):
- A **page** describing the service + a **form** (name/email/upload/details) that emails the owner
  (Web3Forms/Tally/Jotform — free form-to-email; downsize uploads client-side so big files deliver).
- A **manual evaluate → quote → deliver** loop (reply from the store email; take payment via a
  draft-order invoice or a simple service product).
- Free evaluation as the hook; real price after. Publish the page + add a nav item once the store
  token is set up.

This turns an existing skill (photo cleanup, custom design, etc.) into revenue without waiting on
product-search traffic.
