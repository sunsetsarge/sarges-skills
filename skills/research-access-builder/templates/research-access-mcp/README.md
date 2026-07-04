# research-access-mcp

A stdio MCP server for academic paper search and legal open-access PDF download. Fans out
to OpenAlex, Crossref, Semantic Scholar, arXiv, and Europe PMC; resolves legal OA PDFs via
Unpaywall / CORE / arXiv / Europe PMC; never suggests or performs paywall bypass.

## Requirements

- Python 3.10+ (target: 3.12)
- `pip install -r requirements.txt`

## Environment variables

| Variable | Required? | Purpose |
|---|---|---|
| `UNPAYWALL_EMAIL` | **Yes**, for `find_open_access_pdf`/`download_pdf` | Unpaywall's API terms require a contact email. Without it, Unpaywall calls are refused with a clear message. |
| `RESEARCH_PDF_DIR` | No (default `~/Documents/Papers`) | Where downloaded PDFs are saved. |
| `SERPAPI_API_KEY` | No | Enables `google_scholar_search` via SerpApi (free tier: 250 searches/month) instead of the best-effort `scholarly` scrape. |
| `CORE_API_KEY` | No | Enables CORE as a fallback OA-PDF source. Free signup at core.ac.uk/services/api. |
| `SEMANTIC_SCHOLAR_API_KEY` | No | Raises Semantic Scholar's rate limit from the shared keyless pool. |
| `OPENALEX_API_KEY` | No | Raises OpenAlex's daily usage budget (~10x) under its Feb 2026 budget model. |

No credentials are ever hardcoded in this codebase — everything comes from the environment.

## Tools

- `search_papers(query, author=None, year_from=None, year_to=None, venue=None, limit=10, sources=None)`
- `get_paper_by_doi(doi)`
- `find_open_access_pdf(doi=None, title=None)`
- `download_pdf(doi=None, pdf_url=None, title=None)`
- `download_batch(dois)`
- `export_bibtex(dois, format="bibtex")` (or `format="ris"`)
- `google_scholar_search(query, limit=10)` (best-effort; see below)

## Google Scholar caveat

Google Scholar has no official API. If `SERPAPI_API_KEY` is set, we use SerpApi's
`google_scholar` engine. Otherwise we attempt a best-effort scrape via the optional
`scholarly` package (not installed by default — see `requirements.txt`). On any block or
failure, the tool returns a structured payload:

```json
{
  "status": "blocked_or_unavailable",
  "manual_url": "https://scholar.google.com/scholar?q=...",
  "instructions": "Open this URL in your browser, then paste back a DOI or PDF link; use get_paper_by_doi / download_pdf to continue."
}
```

## Legal-content policy

`find_open_access_pdf` and `download_pdf` only ever return links Unpaywall, CORE, arXiv,
or Europe PMC report as legally open access. If no such link exists, you get the DOI
landing page and `pdf_available: false` — never a paywall-bypass suggestion.

## Testing

```
set UNPAYWALL_EMAIL=you@example.com
set RESEARCH_PDF_DIR=%TEMP%\research-access-test
python test_slice1.py
```

## Registering with Claude Code

```
claude mcp add research-access -- <path-to-venv-python> <path-to-this-dir>\server.py
```

## Cache and logs

- SQLite cache: `%LOCALAPPDATA%\research-access\cache.db` (7-day TTL for searches, 30-day for DOI metadata).
- JSONL structured log: `%LOCALAPPDATA%\research-access\log.jsonl`.
