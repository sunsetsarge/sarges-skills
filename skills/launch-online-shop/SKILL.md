---
name: launch-online-shop
argument-hint: "[platform] [product-type]  e.g. 'etsy pod tees'"
description: >
  End-to-end playbook for launching or scaling a print-on-demand / e-commerce shop:
  platform setup (Printify -> Shopify/Etsy), a curated product pipeline via API,
  conversion copy + SEO, value pricing, mockup QA, a fail-closed trademark
  pre-publish safety gate, and a demand-first launch + first-sales sequence.
  Use when the user wants to start / set up / launch / open an online shop, store,
  or e-commerce / print-on-demand / POD / dropshipping business; create, bulk-create,
  or publish products; write listing titles / tags / descriptions; price a catalog;
  vet a design or brand for trademark risk before selling; build a review/approval
  gallery; or plan a store launch and the marketing that earns the first sales.
  Encodes hard-won lessons from the Saspan Salt build (Printify API gotchas,
  back-print geometry, delete-and-recreate on error 8253, demand-before-scale).
  NOT for: generating the artwork itself (that is vintage-ad-generator / ComfyUI),
  harvesting source images (digitalnc-harvest), or legal advice.
---

# Launch an Online Shop — POD / e-commerce playbook

Distilled from the Saspan Salt build (vintage-newspaper-ad apparel on Printify -> Shopify + Etsy).
The mechanics generalize to any print-on-demand or small e-commerce catalog. **Follow the phase
gates in order — most POD failures come from skipping straight to "make 200 products."**

## The one principle that overrides everything

**Live ≠ earning. Demand before scale.** A polished store with no traffic earns $0. Do NOT
build a giant catalog before proving anyone wants it. The correct sequence is: a *small curated
batch* → real listings on a search-traffic channel → measure → only then scale the winners.
Saspan had 219 products and **~1 self-test order**; the lesson was paid for. Bake a **demand
governor** into any "scale up" step (e.g., "no new bulk designs until ≥10 organic sales").

Say the honest version out loud to the user: "passive income today" is not real; publishing
today means first sale in days-to-weeks, and the first 1–3 sales are the hard ones.

## Phase playbook (gates, not suggestions)

**Phase 0 — Frame & pick the lane.** Confirm: what's the product, who searches for it, which
channel. **Etsy = built-in search traffic** (best for discovery); **Shopify = your own store**
(needs traffic you bring). Most POD starts should lead with Etsy. Write the honest expectations
down. → owner does the ~15-min account/billing/OAuth steps (you can't).

**Phase 1 — Platform + fulfillment wiring.** Printify as the print/fulfillment layer, connected
to the sales channel. Confirm the **production-partner disclosure** is ON (Etsy requires POD
disclosure) and shipping profiles pulled. Secrets via a config loader, never hardcoded.
→ see `references/platform-and-pipeline.md`.

**Phase 2 — TRADEMARK GATE (fail-closed).** Before any design becomes a product, run every brand
name through `scripts/tm_gate.py`. RED (famous/active mark) = blocked; AMBER = 30-sec human
USPTO/Justia Class-25 check; nothing auto-passes. Copyright-public-domain artwork does **not**
clear a live trademark. → see `references/trademark-vetting.md`. **This gate is non-negotiable —
one trademark complaint can suspend the whole shop.**

**Phase 3 — Curated product pipeline (small!).** ~15–25 designs, not 200. Create products via the
Printify API (blueprint + provider + variants + print-area geometry). Reuse artwork by image-id;
clone, don't rebuild. → `references/platform-and-pipeline.md` (geometry, mockups, the gotchas).

**Phase 4 — Copy, SEO & pricing.** Channel-specific: **Etsy titles lead with the theme people
search, not the business name**; exactly 13 tags ≤20 chars; first ~160 chars of the description
carry Google SEO. Value-price with a sane margin. → `references/copy-pricing-seo.md`.

**Phase 5 — Mockup QA + review gate.** Verify each mockup actually shows the design, correctly
placed (back-print centered, not clipped). Build a **review gallery** → the owner ticks keepers →
only then publish. Never mass-publish unreviewed. → `references/platform-and-pipeline.md` (QA),
`references/launch-and-marketing.md` (gallery).

**Phase 6 — Launch + first-sales marketing.** Organic-first, geo-targeted. For a local/nostalgia
brand: relevant FB groups + a tiny geo Meta budget; skip cold national Google/FB. A few $/day of
platform ads only to bootstrap the ranking flywheel. → `references/launch-and-marketing.md`.

**Phase 7 — Measure → scale winners / cut duds.** Watch which *themes* convert. Add designs to
winners; cut the rest. Only now expand the catalog — and only past the demand governor.

**Optional add-on — a service alongside products** (e.g., photo restoration): a simple page +
form-to-email + manual quote loop can out-earn low-traffic product sales early.
→ `references/launch-and-marketing.md`.

## Hard-won gotchas (the scar tissue — read before touching the API)

- **`external` field = the truth about "is it published"**, not `is_locked`/`visible`.
- **Error 8253 "cannot swap images on an existing product"** → you must **delete + recreate**,
  not update-in-place, to change a product's artwork.
- **Error 8253 "Provided images do not exist"** on update → a placeholder (often **neck**) holds a
  **deleted image id**. Only send `back`/`front` placeholders; drop orphaned ones.
- **Back-print geometry**: full-width `scale=1.0` can clip tall designs; center + shrink
  (`x=0.5, y=0.5, scale≈0.80`) so the whole design shows with margins. Verify per-design —
  aspect ratios vary; never blanket-overwrite hand-tuned placements.
- **Dark vs light tees use different artwork files** (white-ink for dark) → the *same* x/y/scale
  does NOT translate between them. Tune each.
- **Stickers (blueprint 400) don't generate Printify mockups** → make your own product photos and
  wire them into the gallery via `file:///` paths.
- **Mockup image labels differ by shop**: Etsy tags images `position=back`; Shopify tags them
  `position=other` with `camera_label=back-2` in the URL. Match on `camera_label=back` substring.
- **USPTO has no clean free name-search API** (the `tmsearch.uspto.gov/api-*` path is S3 storage).
  The reliable trademark step is the prefilled human worklist in `tm_gate.py`.
- **A published product may 500 on any update** (a Printify-side per-product lock) — even a
  title no-op fails. Retry later; don't assume your payload is wrong.
- Model/agent spend: bulk work is cheap main-loop file/API calls — don't fan out subagents for it.

## Standing guardrails (carry into every phase)

- **Never mention public domain / source archives / DigitalNC in customer-facing copy.**
- **IP:** no real logos or post-1928 brand scans reproduced as products; run the trademark gate.
- **Approval gates:** publishing is owner-visible/outward-facing — build the review gallery and get
  a human yes before anything goes live. Delete/recreate only what you created.

## Scripts

- `scripts/tm_gate.py` — the fail-closed trademark pre-publish gate (Phase 2). Standalone, stdlib-only.
- `scripts/README.md` — index of the Saspan reference implementations (create/clone products,
  re-center back prints, build the review gallery, the secrets loader) to adapt for a new shop.

## References (load the one for the phase you're in)

- `references/platform-and-pipeline.md` — accounts, Printify↔channel wiring, product creation,
  geometry, mockups, QA, and the full API-gotchas detail.
- `references/copy-pricing-seo.md` — Etsy vs Shopify title/tag/description formulas + value pricing.
- `references/trademark-vetting.md` — the copyright-vs-trademark gate, the checklist, and how to
  run `tm_gate.py` (the spec behind the script).
- `references/launch-and-marketing.md` — review-gallery approval gate, demand-first launch,
  organic/geo marketing, and the service-add-on pattern.
