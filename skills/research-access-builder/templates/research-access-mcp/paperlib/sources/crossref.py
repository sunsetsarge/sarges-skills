"""Crossref source adapter.

Verified 2026-07-04: GET https://api.crossref.org/works?query.bibliographic=...&rows=N&mailto=EMAIL
+ polite User-Agent works keyless (200 OK probed). Dec 2025 polite-pool limits: 10 r/s
single-record, 3 r/s list queries, 3 concurrent. We honor X-Rate-Limit-Limit /
X-Rate-Limit-Interval response headers dynamically via a module-level hint (best effort;
http_client's static per-host interval is the floor).
"""

from .. import config, http_client
from ..models import Paper


def _item_to_paper(item: dict) -> Paper:
    authors = []
    for a in (item.get("author") or []):
        given = a.get("given", "")
        family = a.get("family", "")
        name = " ".join(p for p in (given, family) if p).strip()
        if name:
            authors.append(name)

    title_list = item.get("title") or []
    title = title_list[0] if title_list else ""

    year = None
    for date_field in ("published-print", "published-online", "published", "issued"):
        d = item.get(date_field)
        if d and d.get("date-parts") and d["date-parts"][0]:
            year = d["date-parts"][0][0]
            break

    venue = ""
    container = item.get("container-title") or []
    if container:
        venue = container[0]

    doi = Paper.normalize_doi(item.get("DOI", ""))

    return Paper(
        title=title,
        authors=authors,
        year=year,
        venue=venue,
        abstract=item.get("abstract", "") or "",
        doi=doi,
        citation_count=item.get("is-referenced-by-count") or 0,
        oa_status="",
        pdf_url="",
        urls={"crossref": item.get("URL", "")} if item.get("URL") else {},
        source="crossref",
    )


def _headers() -> dict:
    return {}  # User-Agent already set globally in http_client with polite string


def search(query: str, limit: int = 10) -> tuple:
    try:
        params = {"query.bibliographic": query, "rows": min(limit, 100)}
        if config.CONTACT_EMAIL:
            params["mailto"] = config.CONTACT_EMAIL
        resp = http_client.get(
            "https://api.crossref.org/works", params=params, headers=_headers()
        )
        if resp.status_code != 200:
            return [], {"status": "error", "http_status": resp.status_code}
        data = resp.json()
        items = (data.get("message") or {}).get("items") or []
        papers = [_item_to_paper(it).to_dict() for it in items[:limit]]
        return papers, {"status": "ok", "count": len(papers)}
    except Exception as exc:
        return [], {"status": "error", "error": str(exc)}


def get_by_doi(doi: str) -> tuple:
    try:
        doi_norm = Paper.normalize_doi(doi)
        params = {}
        if config.CONTACT_EMAIL:
            params["mailto"] = config.CONTACT_EMAIL
        resp = http_client.get(
            f"https://api.crossref.org/works/{doi_norm}", params=params, headers=_headers()
        )
        if resp.status_code != 200:
            return None, {"status": "error", "http_status": resp.status_code}
        data = resp.json()
        item = data.get("message") or {}
        return _item_to_paper(item).to_dict(), {"status": "ok"}
    except Exception as exc:
        return None, {"status": "error", "error": str(exc)}


def raw_item_by_doi(doi: str):
    """Return the raw Crossref message dict (used by bibtex.py for richer field access)."""
    try:
        doi_norm = Paper.normalize_doi(doi)
        params = {}
        if config.CONTACT_EMAIL:
            params["mailto"] = config.CONTACT_EMAIL
        resp = http_client.get(
            f"https://api.crossref.org/works/{doi_norm}", params=params, headers=_headers()
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        return data.get("message")
    except Exception:
        return None
