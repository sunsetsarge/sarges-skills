"""Semantic Scholar source adapter.

PROBED 2026-07-04: keyless shared pool returned 429 immediately on search. S2 must NEVER
be the sole source for anything — treat 429 as a soft-fail with max 2 retries (short
backoff), then give up quietly. Optional key env SEMANTIC_SCHOLAR_API_KEY sent as header
x-api-key (1 r/s on search with key). Cap limit+offset <= 1000.
"""

import time

from .. import config, http_client
from ..models import Paper

_MAX_SOFT_RETRIES = 2


def _paper_to_paper(item: dict) -> Paper:
    authors = [a.get("name", "") for a in (item.get("authors") or []) if a.get("name")]
    external_ids = item.get("externalIds") or {}
    doi = Paper.normalize_doi(external_ids.get("DOI", "") or "")

    oa_pdf = item.get("openAccessPdf") or {}
    pdf_url = oa_pdf.get("url", "") if isinstance(oa_pdf, dict) else ""

    return Paper(
        title=item.get("title") or "",
        authors=authors,
        year=item.get("year"),
        venue=item.get("venue") or "",
        abstract=item.get("abstract") or "",
        doi=doi,
        citation_count=item.get("citationCount") or 0,
        oa_status="oa" if item.get("isOpenAccess") else "",
        pdf_url=pdf_url,
        urls={"semanticScholar": item.get("paperId", "")} if item.get("paperId") else {},
        source="semantic_scholar",
    )


def _headers() -> dict:
    h = {}
    if config.SEMANTIC_SCHOLAR_API_KEY:
        h["x-api-key"] = config.SEMANTIC_SCHOLAR_API_KEY
    return h


def search(query: str, limit: int = 10) -> tuple:
    fields = "title,year,authors,venue,abstract,citationCount,externalIds,isOpenAccess,openAccessPdf"
    params = {"query": query, "limit": min(limit, 100), "fields": fields}

    last_status = None
    for attempt in range(_MAX_SOFT_RETRIES + 1):
        try:
            resp = http_client.get(
                "https://api.semanticscholar.org/graph/v1/paper/search",
                params=params,
                headers=_headers(),
                max_retries=0,  # we handle 429 backoff ourselves here, briefly
            )
            if resp.status_code == 429:
                last_status = 429
                if attempt < _MAX_SOFT_RETRIES:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                return [], {"status": "rate_limited", "http_status": 429}
            if resp.status_code != 200:
                return [], {"status": "error", "http_status": resp.status_code}
            data = resp.json()
            items = data.get("data") or []
            papers = [_paper_to_paper(it).to_dict() for it in items[:limit]]
            return papers, {"status": "ok", "count": len(papers)}
        except Exception as exc:
            last_status = str(exc)
            if attempt < _MAX_SOFT_RETRIES:
                time.sleep(1.0)
                continue
            return [], {"status": "error", "error": last_status}
    return [], {"status": "error", "error": str(last_status)}
