"""OpenAlex source adapter.

Verified 2026-07-04: GET https://api.openalex.org/works?search=...&per-page=N&mailto=EMAIL
works keyless (200 OK probed). OpenAlex moved to a usage-budget model Feb 2026; an API key
(env OPENALEX_API_KEY, sent as api_key query param) raises the daily budget ~10x. Schema is
in flux — defensive .get() everywhere.
"""

from .. import config, http_client
from ..models import Paper


def _reconstruct_abstract(inverted_index) -> str:
    if not inverted_index or not isinstance(inverted_index, dict):
        return ""
    try:
        positions = []
        for word, idxs in inverted_index.items():
            for i in idxs:
                positions.append((i, word))
        positions.sort(key=lambda p: p[0])
        return " ".join(w for _, w in positions)
    except Exception:
        return ""


def _work_to_paper(work: dict) -> Paper:
    authors = []
    for a in (work.get("authorships") or []):
        name = (a.get("author") or {}).get("display_name")
        if name:
            authors.append(name)

    doi_url = work.get("doi") or ""
    doi = Paper.normalize_doi(doi_url)

    venue = ""
    primary_location = work.get("primary_location") or {}
    source_info = primary_location.get("source") or {}
    if isinstance(source_info, dict):
        venue = source_info.get("display_name") or ""

    oa = work.get("open_access") or {}
    oa_status = "oa" if oa.get("is_oa") else ""
    pdf_url = oa.get("oa_url") or ""

    return Paper(
        title=work.get("display_name") or work.get("title") or "",
        authors=authors,
        year=work.get("publication_year"),
        venue=venue,
        abstract=_reconstruct_abstract(work.get("abstract_inverted_index")),
        doi=doi,
        citation_count=work.get("cited_by_count") or 0,
        oa_status=oa_status,
        pdf_url=pdf_url,
        urls={"openalex": work.get("id", "")} if work.get("id") else {},
        source="openalex",
    )


def _params(base: dict) -> dict:
    p = dict(base)
    if config.CONTACT_EMAIL:
        p["mailto"] = config.CONTACT_EMAIL
    if config.OPENALEX_API_KEY:
        p["api_key"] = config.OPENALEX_API_KEY
    return p


def search(query: str, limit: int = 10) -> tuple:
    """Returns (list_of_paper_dicts, status_dict)."""
    try:
        resp = http_client.get(
            "https://api.openalex.org/works",
            params=_params({"search": query, "per-page": min(limit, 200)}),
        )
        if resp.status_code != 200:
            return [], {"status": "error", "http_status": resp.status_code}
        data = resp.json()
        results = data.get("results") or []
        papers = [_work_to_paper(w).to_dict() for w in results[:limit]]
        return papers, {"status": "ok", "count": len(papers)}
    except Exception as exc:
        return [], {"status": "error", "error": str(exc)}


def get_by_doi(doi: str) -> tuple:
    """Returns (paper_dict_or_None, status_dict)."""
    try:
        doi_norm = Paper.normalize_doi(doi)
        resp = http_client.get(
            f"https://api.openalex.org/works/doi:{doi_norm}",
            params=_params({}),
        )
        if resp.status_code != 200:
            return None, {"status": "error", "http_status": resp.status_code}
        work = resp.json()
        return _work_to_paper(work).to_dict(), {"status": "ok"}
    except Exception as exc:
        return None, {"status": "error", "error": str(exc)}
