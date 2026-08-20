# Research-access data sources

All facts below were live-verified 2026-07-04 unless flagged otherwise. Do not trust older
training knowledge about these APIs — they drift (OpenAlex's monetization shift and arXiv's
tightened rate limits both landed in Feb 2026).

## OpenAlex — primary search source

- **Good for**: broad scholarly-work search/enrichment (citation counts, OA status, venue).
- **Base URL**: `https://api.openalex.org/works`
- **Auth**: none required today. Optional `OPENALEX_API_KEY` env, sent as `api_key` query
  param, raises the daily usage budget ~10x.
- **Rate limits**: keyless access probed 200 OK (verified 2026-07-04). **Monetization note**:
  OpenAlex moved to a usage-budget model in Feb 2026 (see developers.openalex.org) — the
  keyless tier still works but has a daily budget ceiling; a free key is recommended for any
  sustained use.
- **Schema stability**: in flux — code uses defensive `.get()` everywhere and tolerates
  missing/renamed fields.
- **Routing role**: primary (search fan-out + DOI enrichment).

## Crossref — primary search source

- **Good for**: authoritative bibliographic metadata (title, authors, venue, DOI, citation
  counts via `is-referenced-by-count`).
- **Base URL**: `https://api.crossref.org/works`
- **Auth**: none required. Polite pool access via `mailto` query param + polite User-Agent
  string (`research-access-mcp/0.1 (...; mailto:EMAIL)`).
- **Rate limits (Dec 2025 policy, verified 2026-07-04 reachable)**: polite pool = 10 req/s
  for single-record lookups, 3 req/s for list queries, 3 concurrent connections. The server
  also returns `X-Rate-Limit-Limit` / `X-Rate-Limit-Interval` headers — honor these
  dynamically where possible (the shipped `http_client.py` per-host static interval is a
  conservative floor under this).
- **Routing role**: primary (search fan-out) + primary source for `get_paper_by_doi` and
  BibTeX export.

## Semantic Scholar — enrich (best-effort)

- **Good for**: additional citation counts, abstracts, `openAccessPdf` hints.
- **Base URL**: `https://api.semanticscholar.org/graph/v1/paper/search`
- **Auth**: optional `SEMANTIC_SCHOLAR_API_KEY` env, sent as header `x-api-key` (1 req/s on
  search with a key).
- **Rate limits**: **PROBED 2026-07-04 — the keyless shared pool returned HTTP 429
  immediately** on a search request. This source must never be the sole source for any
  operation. The adapter treats 429 as a soft-fail (max 2 retries, short backoff) and moves
  on without failing the caller.
- **Routing role**: enrich only, best-effort. Search fan-out includes it by default but
  tolerates total failure.

## arXiv — resolver / preprint search

- **Good for**: preprint search and PDFs for CS/physics/math/stats/quant papers.
- **Base URL**: `http://export.arxiv.org/api/query` (Atom XML; parsed with stdlib
  `xml.etree`, no extra dependency)
- **Auth**: none.
- **Rate limits / etiquette**: >=3 seconds between requests, PLUS exponential backoff on
  429 — **arXiv tightened limits in Feb 2026 and 429s were observed even at 3s spacing**
  (unverified quantitatively in this session's live probe, per spec guidance; code assumes
  this is possible and retries defensively).
- **PDF access**: `https://arxiv.org/pdf/{id}` — probed 200 OK, `Content-Type:
  application/pdf`, extensionless form works.
- **Routing role**: resolver (OA-PDF chain) + optional search-fan-out source.

## Europe PMC — resolver / biomed search

- **Good for**: biomedical/life-sciences literature, reliable OA-PDF flags.
- **Base URL**: `https://www.ebi.ac.uk/europepmc/webservices/rest/search`
- **Auth**: none.
- **Rate limits**: ~10 req/s is community-reported (**not an officially documented SLA —
  flagged unverified**); the shipped client throttles to 1 req/s to be safe.
- **OA PDF extraction**: scan `fullTextUrlList.fullTextUrl[]` for
  `availabilityCode=="OA" && documentStyle=="pdf"`, preferring `site=="Europe_PMC"`.
- **Routing role**: resolver (OA-PDF chain fallback) + optional search-fan-out source.

## Unpaywall — primary OA-PDF resolver

- **Good for**: the single best source of legal OA PDF links, keyed by DOI.
- **Base URL**: `https://api.unpaywall.org/v2/{doi}`
- **Auth**: `email` query param is **required** by Unpaywall's terms. Wired to env
  `UNPAYWALL_EMAIL`; if unset, the tool refuses the call with a clear message rather than
  guessing or hardcoding an email.
- **Rate limits**: 100,000 requests/day.
- **CRITICAL field-shape gotcha (probed 2026-07-04)**: `best_oa_location.url_for_pdf` is
  frequently `null` even for gold OA records. The resolver must scan `best_oa_location`
  FIRST, then every entry in `oa_locations[]`, for a non-null `url_for_pdf`. If none exist,
  fall back to a location's plain `url` ONLY if a HEAD request confirms
  `Content-Type: application/pdf`; otherwise return the landing page with
  `pdf_available: false`.
- **Routing role**: primary resolver, first in the OA-PDF chain.

## CORE v3 — resolver fallback (key required)

- **Good for**: aggregated repository/OA fulltext, particularly for papers Unpaywall misses.
- **Base URL**: `https://api.core.ac.uk/v3/search/works`
- **Auth**: `Authorization: Bearer {CORE_API_KEY}` — **required**. Free signup at
  core.ac.uk/services/api. If `CORE_API_KEY` is unset, CORE is skipped silently (not a hard
  failure).
- **Rate limits**: token-based quota system; **numeric quotas are unverified in this
  session** — CORE's public docs have been intermittently 403-blocked to automated
  fetchers, so treat any specific req/min number as unconfirmed. The shipped client is
  deliberately gentle (~1 request per 2 seconds).
- **Routing role**: resolver fallback, second in the OA-PDF chain, only when a key is
  configured.

## Google Scholar — best-effort only, no API

- **Good for**: broadest possible coverage, citation-graph browsing — but only as a
  human-assisted last resort.
- **No official API exists.** Two supported paths:
  1. **SerpApi** (`SERPAPI_API_KEY` set): `GET https://serpapi.com/search?engine=google_scholar`.
     Free tier: 250 searches/month.
  2. **`scholarly` package** (optional, NOT installed by default — commented out in
     `requirements.txt`): PyPI version 1.7.11 is roughly 18 months stale, and Google's
     blocking of scraping is persistent and well documented. Uses a `FreeProxies` proxy
     generator; block/failure detection triggers a manual-fallback payload rather than a
     raised exception.
- **Manual fallback payload shape**:
  ```json
  {
    "status": "blocked_or_unavailable",
    "manual_url": "https://scholar.google.com/scholar?q=<urlencoded query>",
    "instructions": "Open this URL in your browser, then paste back a DOI or PDF link; use get_paper_by_doi / download_pdf to continue."
  }
  ```
- **Routing role**: best-effort only, never load-bearing for any other tool.

## Cross-cutting engineering notes

- Single `httpx` client wrapper (`http_client.py`) applies a per-host minimum request
  interval (monotonic clock), retries (max 3) with exponential backoff + jitter on 429/5xx,
  a 30-second per-source timeout, and a polite `User-Agent` on every call.
- SQLite cache (`cache.py`) at `%LOCALAPPDATA%\research-access\cache.db`: 7-day TTL for
  searches, 30-day TTL for DOI metadata, keyed by normalized query/DOI + source.
- JSONL structured log (`logging_util.py`) at `%LOCALAPPDATA%\research-access\log.jsonl`:
  one record per operation.
- Zero hardcoded API keys or emails anywhere in the codebase — everything is read from
  environment variables in `config.py`.
