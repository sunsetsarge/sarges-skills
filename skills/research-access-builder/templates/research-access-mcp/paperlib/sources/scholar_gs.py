"""Google Scholar adapter — best-effort ONLY (Slice 3).

Google Scholar has no official API. The `scholarly` package is stale (v1.7.11 on PyPI,
~18 months old) and Google's blocking of scrapers is persistent and well documented.
This adapter:
  1. If SERPAPI_API_KEY is set, uses SerpApi's google_scholar engine (free tier 250/mo).
  2. Otherwise, guarded-imports `scholarly` with a FreeProxies generator and tries a scrape.
  3. On any failure/block, returns a structured manual-fallback payload instead of raising.

`scholarly` is NOT a hard dependency — it is commented out in requirements.txt. If it is
not installed, we skip straight to the manual-fallback payload.
"""

import urllib.parse

from .. import config, http_client
from ..models import Paper


def _manual_fallback(query: str, reason: str = "blocked_or_unavailable") -> dict:
    encoded = urllib.parse.quote_plus(query)
    return {
        "status": reason,
        "manual_url": f"https://scholar.google.com/scholar?q={encoded}",
        "instructions": (
            "Open this URL in your browser, then paste back a DOI or PDF link; "
            "use get_paper_by_doi / download_pdf to continue."
        ),
    }


def _via_serpapi(query: str, limit: int) -> tuple:
    try:
        resp = http_client.get(
            "https://serpapi.com/search",
            params={
                "engine": "google_scholar",
                "q": query,
                "api_key": config.SERPAPI_API_KEY,
                "num": min(limit, 20),
            },
        )
        if resp.status_code != 200:
            return [], _manual_fallback(query, "serpapi_error")
        data = resp.json()
        organic = data.get("organic_results") or []
        papers = []
        for item in organic[:limit]:
            pub_info = item.get("publication_info") or {}
            authors = []
            for a in pub_info.get("authors") or []:
                name = a.get("name")
                if name:
                    authors.append(name)
            resources = item.get("resources") or []
            pdf_url = ""
            for r in resources:
                if (r.get("file_format") or "").upper() == "PDF":
                    pdf_url = r.get("link", "")
                    break
            papers.append(
                Paper(
                    title=item.get("title", "") or "",
                    authors=authors,
                    year=None,
                    venue=pub_info.get("summary", "") or "",
                    abstract=item.get("snippet", "") or "",
                    doi="",
                    citation_count=(item.get("inline_links", {}) or {})
                    .get("cited_by", {})
                    .get("total", 0)
                    or 0,
                    oa_status="oa" if pdf_url else "",
                    pdf_url=pdf_url,
                    urls={"google_scholar": item.get("link", "")} if item.get("link") else {},
                    source="google_scholar",
                ).to_dict()
            )
        return papers, {"status": "ok", "count": len(papers), "via": "serpapi"}
    except Exception as exc:
        return [], _manual_fallback(query, f"serpapi_exception:{exc}")


def _via_scholarly(query: str, limit: int) -> tuple:
    try:
        from scholarly import scholarly, ProxyGenerator  # type: ignore
    except ImportError:
        return [], _manual_fallback(query, "scholarly_not_installed")

    try:
        pg = ProxyGenerator()
        pg.FreeProxies()
        scholarly.use_proxy(pg)

        search_gen = scholarly.search_pubs(query)
        papers = []
        for _ in range(limit):
            try:
                pub = next(search_gen)
            except StopIteration:
                break
            bib = pub.get("bib", {}) if isinstance(pub, dict) else {}
            papers.append(
                Paper(
                    title=bib.get("title", "") or "",
                    authors=bib.get("author", []) if isinstance(bib.get("author"), list) else [],
                    year=bib.get("pub_year"),
                    venue=bib.get("venue", "") or "",
                    abstract=bib.get("abstract", "") or "",
                    doi="",
                    citation_count=pub.get("num_citations", 0) or 0,
                    oa_status="",
                    pdf_url=pub.get("eprint_url", "") or "",
                    urls={"google_scholar": pub.get("pub_url", "")} if pub.get("pub_url") else {},
                    source="google_scholar",
                ).to_dict()
            )
        if not papers:
            return [], _manual_fallback(query, "no_results_or_blocked")
        return papers, {"status": "ok", "count": len(papers), "via": "scholarly"}
    except Exception as exc:
        return [], _manual_fallback(query, f"scholarly_exception:{exc}")


def search(query: str, limit: int = 10) -> tuple:
    if config.SERPAPI_API_KEY:
        return _via_serpapi(query, limit)
    return _via_scholarly(query, limit)
