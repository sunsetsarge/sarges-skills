---
name: digitalnc-harvest
description: Harvest vintage public-domain newspaper pages and advertisements from DigitalNC and the LOC Chronicling America API for the Saspan Salt print-on-demand pipeline. Use whenever the user mentions saspan, digitalnc, chronam, chronicling america, loc.gov, IIIF newspaper download, vintage newspaper ads, ALTO OCR, newspaper harvest, or the ad extractor / ad reviewer / ad selector pipeline. Wraps the validated digitalnc_dl.py and chronam_dl.py downloaders plus the existing extraction pipeline — DO NOT rebuild these from scratch.
---

# DigitalNC / Chronicling America Newspaper Harvest

Sources public-domain vintage newspaper pages, extracts advertisements, and feeds them into the Saspan Salt POD pipeline. This skill **wraps existing, validated scripts** — its job is to run them correctly and avoid the failures already discovered, not to reimplement them.

## ⛔ DO NOT REBUILD — existing scripts (validated, contract-tested)

| Script | Location | Purpose |
|---|---|---|
| `digitalnc_dl.py` | `D:\DigitalNC_Newspapers\` | DigitalNC downloader (`info`, `download --start --end --max --last-pages --all-pages --ocr`) |
| `chronam_dl.py` | `D:\Claude Projects\Saspan Salt Vintage Prints\` | LOC Chronicling America downloader, same CLI shape |
| `ad_extractor.py` | `C:\Claude\Scripts\Python\` (+ Newspaper Cropper) | Auto-detect ads (morphology + pHash + quality ranking) |
| `ad_reviewer.py` | Newspaper Cropper project | Interactive KEEP/SKIP quality review |
| `ad_selector.py` | Newspaper Cropper project | Manual page browser, click-drag selection, OCR |
| `loc_jp2_downloader.py` | `C:\Claude\Scripts\Python\` | Full-res JP2 fetch |

Before writing ANY new downloader/extractor, audit these folders first. The downloaders are contract-tested (`test_digitalnc_dl.py`, `test_chronam_dl.py`).

## Workflow

```
discover/download (digitalnc_dl | chronam_dl)
   → extract ads (ad_extractor)
   → KEEP/SKIP triage  ← local VLM first, Haiku escalation (see Model tiering)
   → human Gate A (ad_reviewer)
   → into Saspan pipeline (D:\SaspanPipeline\ ledger)
```

## ⚠️ Run on the HOST, not in a sandbox

`loc.gov` and `digitalnc.org` are excluded from the Cowork sandbox allowlist → every request returns **proxy 403**. Run all live-network harvesting from the host (Bash tool on the user's machine / Desktop Commander / `cmd`), never from a sandboxed workspace shell.

## DigitalNC endpoint map (verified live, no auth)

Open ONI (chronam fork) + RAIS IIIF level-2 image server.

| Purpose | URL |
|---|---|
| All titles (2,188) | `/newspapers.json` |
| Title metadata | `/lccn/{lccn}.json` → `manifests[]` = issues |
| Issue manifest | `/lccn/{lccn}/{YYYY-MM-DD}/ed-1.json` → `sequences[0].canvases[]` = pages |
| Page metadata | `/lccn/{lccn}/{date}/ed-1/seq-{N}.json` → read `images[0].resource.service.@id` |
| Page OCR text | `/lccn/{lccn}/{date}/ed-1/seq-{N}/ocr.txt` |
| Page ALTO XML | `/lccn/{lccn}/{date}/ed-1/seq-{N}/ocr.xml` (word coordinates) |
| Page JP2 / PDF | `/lccn/{lccn}/{date}/ed-1/seq-{N}.jp2` / `.pdf` |
| IIIF sized JPEG | `{service_id}/full/{width},/0/default.jpg` — use **width=4000** for 13.3"×17.7" @ 300 DPI |
| Page text search | `/search/pages/results/list/?andtext={q}&format=json` — **trailing `list/` required** |

Search caveat: quoted "exact phrase" in `andtext` does NOT work; use `proxtext=` + `proxdistance=` for proximity.

## LOC Chronicling America (verified)

The standalone `chroniclingamerica.loc.gov` API was retired in 2025 — everything goes through `loc.gov` JSON API, no auth.

- **Working facet (the only one):** `https://www.loc.gov/collections/chronicling-america/?fa=number_lccn:{lccn}&fo=json`
- Date-narrow server-side: `&dates=YYYY/YYYY` (orders of magnitude faster than client-side)
- Per-issue pages: `&fa=number_lccn:{lccn}|dates:{YYYY-MM-DD}`
- **IIIF size rewrite (the trap):** search results embed `pct:6.25` thumbnails. For full res:
  `re.sub(r"/full/[^/]+/0/default\.jpg", "/full/4000,/0/default.jpg", url)`
- **Facets that DON'T work:** `partof_title:` (times out), `partof:` (0 results), `aka:` (1M false matches). Only `number_lccn:` is correct.

## Output contract (both downloaders share it)

```
D:\DigitalNC_Newspapers\{lccn}\
    {lccn}_{YYYYMMDD}_p{N}of{TOTAL}.jpg
    {lccn}_{YYYYMMDD}_p{N}of{TOTAL}.txt   (digitalnc_dl --ocr only)
    manifest.jsonl                         (one row per page)
    .cache\                                (chronam_dl — search-page JSON for resume)
```

`manifest.jsonl` row: `{"lccn","date","page","total_pages","ok","file","ts"}`
Additive optional: `source:"loc-chronam"` (chronam), `ocr_ok:true|false` (digitalnc --ocr).

## Resilience rules (baked into both downloaders — preserve on any edit)

- **Catch `requests.exceptions.ChunkedEncodingError`** in the retry loop (8s backoff). Both hosts drop mid-stream often; enumeration crashes without it.
- **Force full read** of non-stream responses inside `polite_get` so chunked drops surface in the retry loop, not the caller's `.json()`.
- **Cache search pages to disk** → resume reads cached pages, fetches only missing ones.
- **4s polite delay** + descriptive UA (LOC asks <20 req/min; DigitalNC is a small nonprofit).
- **Skip-if-exists** on every download (resume-safe).
- **PD hard cap 1927** (`end_year` clamps server-side) — belt-and-suspenders for public-domain scope.
- `info` command: use `at=results,pagination`, fetch 1 result, read `pagination.total` — never paginate a 6,000-issue title client-side.

## Gotchas table

| Symptom | Cause | Fix |
|---|---|---|
| Every URL returns proxy 403 | sandbox allowlist excludes the hosts | run from host, not sandbox |
| LOC returns 0 for a good LCCN | wrong facet | use `fa=number_lccn:{lccn}` |
| JPEG < 100 KB | IIIF URL still `pct:6.25` | rewrite to `/full/4000,/0/default.jpg` |
| Crash mid-enumeration (`IncompleteRead`) | TCP drop not caught | add `ChunkedEncodingError` to retry |
| Write appears truncated ~360 lines | write-tool size limit | write head + append tail, or split modules |

## Adopt-don't-build (per Workspace Optimization Audit 5)

Before extending the pipeline, prefer these over new code:
- **Newspaper Navigator (LoC)** — pre-extracted ADVERTISEMENT bounding boxes + embeddings for 16.3M ChronAm pages. **Can replace the ad-detection step for the ChronAm corpus** and enables "find more ads like this best-seller." (bcglee.github.io/newspaper-navigator.html)
- **LoC bulk OCR batches** (METS-ALTO + JP2) instead of per-page scraping. (chroniclingamerica.loc.gov/ocr)
- **alto-tools** (`github.com/cneud/alto-tools`) / `alto-xml` — ALTO parsing; word coordinates map OCR text → ad crop regions.
- **iiif-download** (PyPI) — handles per-institution rate limits (Gallica throttles hard) if expanding sources.
- **imagededup** (idealo) for pHash/dHash plumbing in the shared `image_hash.py` module.

## Model tiering (cheap-model operation)

- **KEEP/SKIP ad triage** → local VLM first (Qwen3-VL or Gemma 3 4B multimodal on the 10 GB box, $0), escalate only low-confidence crops to **Haiku**. Never burn Opus/Fable on triage.
- **ALTO→JSON extraction** → local Qwen3 14B with LM Studio Structured Output (GBNF grammar forces valid JSON).
- **Human gates stay human:** Gate A (keeper approval, `ad_reviewer`) and Gate B (pre-publish) are never delegated to any model.
- VRAM contention: don't run the VLM and a ComfyUI upscale at once on 10 GB — sequence the stages.

## Cross-references

- Full API methods & gotchas: Confluence Addendum 10 (page 63209474)
- Saspan Operations Manual: Confluence 65273857 · Pipeline v2: 64749570
- Reference doc on disk: `D:\Claude Projects\Saspan Salt Vintage Prints\NEWSPAPER_API_SOURCES.md`
- Re-validation harnesses: `probe_digitalnc.py`, `probe_loc.py` in the same workspace
