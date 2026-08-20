---
name: research-access
description: Use the installed research-access MCP server to find academic papers, look up a paper by DOI, resolve and download legal open-access PDFs, export BibTeX/RIS citations, and run best-effort Google Scholar searches. Trigger on "find papers on X", "search for research on X", "get the PDF for <DOI/title>", "download this paper", "bibtex for this paper", "literature search on X", "look this up on Google Scholar". This is the day-to-day USER of an already-installed research-access-mcp server — if the MCP server isn't installed yet, use the research-access-builder skill instead to build/install it first.
---

# research-access

Thin usage skill for the `research-access-mcp` server. If its tools
(`search_papers`, `get_paper_by_doi`, `find_open_access_pdf`, `download_pdf`,
`download_batch`, `export_bibtex`, `google_scholar_search`) are not available, the server
isn't installed — use the `research-access-builder` skill to build it first.

## Tools and example calls

### `search_papers(query, author=None, year_from=None, year_to=None, venue=None, limit=10, sources=None)`
Fans out to OpenAlex, Crossref, Semantic Scholar, and Europe PMC; merges/dedupes by
DOI/title; ranks by source authority then citation count. Returns `results` (list of Paper
dicts) and `source_status` (which sources answered/failed/skipped).

```
search_papers(query="CRISPR off-target effects", year_from=2020, limit=15)
```

### `get_paper_by_doi(doi)`
Crossref primary, OpenAlex enrich (citations, OA status).

```
get_paper_by_doi(doi="10.1371/journal.pcbi.1004668")
```

### `find_open_access_pdf(doi=None, title=None)`
Legal-OA resolution chain: Unpaywall -> CORE (if configured) -> arXiv -> Europe PMC. Returns
`pdf_available`, `pdf_url`, `source`, `oa_status`, `license`, `landing_page`. If nothing
legal is found, `pdf_available` is `false` and you get the landing page instead.

```
find_open_access_pdf(doi="10.1371/journal.pcbi.1004668")
```

### `download_pdf(doi=None, pdf_url=None, title=None)`
Resolves if needed, downloads to `RESEARCH_PDF_DIR`, names the file
`AuthorYear_ShortTitle.pdf`, skips if the file already exists, verifies it's a real PDF.

```
download_pdf(doi="10.1371/journal.pcbi.1004668")
```

### `download_batch(dois)`
Same as `download_pdf` but loops a list; reports per-item status; never aborts the whole
batch on one failure.

### `export_bibtex(dois, format="bibtex")`
BibTeX (or `format="ris"`) from Crossref metadata.

```
export_bibtex(dois=["10.1371/journal.pcbi.1004668", "10.1038/s41586-021-03819-2"])
```

### `google_scholar_search(query, limit=10)`
Best-effort. See fallback workflow below.

## Routing strategy (brief)

- **Search** fans out across multiple free scholarly APIs and merges results — no single
  source is authoritative, so `source_status` tells you what actually answered.
- **OA-PDF resolution** always tries Unpaywall first (best legal-OA source keyed by DOI),
  then CORE, then arXiv, then Europe PMC, stopping at the first hit.
- **Semantic Scholar** is enrich-only and best-effort — its shared keyless pool
  rate-limits aggressively; a 429 there never fails the overall search.
- **Google Scholar** has no API at all and is always best-effort (see below).

## Human-in-the-loop Google Scholar fallback

Because Google Scholar has no official API, `google_scholar_search` may return a
manual-fallback payload instead of results:

```json
{
  "status": "blocked_or_unavailable",
  "manual_url": "https://scholar.google.com/scholar?q=...",
  "instructions": "Open this URL in your browser, then paste back a DOI or PDF link; use get_paper_by_doi / download_pdf to continue."
}
```

When you see this: open `manual_url` yourself (or ask the user to), find the relevant
result, and get either its DOI or a direct PDF link from the page. Then call
`get_paper_by_doi` or `download_pdf` with what you found to pick the workflow back up. If
`SERPAPI_API_KEY` is configured on the server, this fallback should rarely trigger.

## Legal-content policy

This toolkit only ever surfaces PDFs that Unpaywall, CORE, arXiv, or Europe PMC report as
legitimately open access. It never attempts, suggests, or assists with paywall bypass
(sci-hub-style mirrors, credential sharing, etc). If no legal OA copy exists, the correct
outcome is `pdf_available: false` plus the publisher's landing page — tell the user that's
the only legally available option, don't look for a workaround.

## Reference material

See `references/sources.md` for per-source details (auth requirements, verified rate
limits, routing role).
