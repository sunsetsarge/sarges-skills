"""Europe PMC source adapter.

Verified 2026-07-04: GET https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=...
&format=json&resultType=core is keyless. OA PDF: in fullTextUrlList.fullTextUrl[] pick
availabilityCode=="OA" && documentStyle=="pdf", prefer site=="Europe_PMC". Rate: ~10 r/s
community-reported (unverified officially) — we use 1 r/s to be safe.
"""

from .. import http_client
from ..models import Paper


def _find_oa_pdf_url(full_text_urls: list) -> str:
    if not full_text_urls:
        return ""
    candidates = [
        u for u in full_text_urls
        if u.get("availabilityCode") == "OA" and u.get("documentStyle") == "pdf"
    ]
    for u in candidates:
        if u.get("site") == "Europe_PMC":
            return u.get("url", "")
    if candidates:
        return candidates[0].get("url", "")
    return ""


def _result_to_paper(item: dict) -> Paper:
    authors = []
    author_string = item.get("authorString", "")
    if author_string:
        authors = [a.strip() for a in author_string.split(",") if a.strip()]

    year = None
    pub_year = item.get("pubYear")
    if pub_year:
        try:
            year = int(pub_year)
        except (ValueError, TypeError):
            pass

    doi = Paper.normalize_doi(item.get("doi", "") or "")

    full_text_list = (item.get("fullTextUrlList") or {}).get("fullTextUrl") or []
    pdf_url = _find_oa_pdf_url(full_text_list)

    return Paper(
        title=item.get("title", "") or "",
        authors=authors,
        year=year,
        venue=item.get("journalTitle", "") or "",
        abstract=item.get("abstractText", "") or "",
        doi=doi,
        citation_count=item.get("citedByCount") or 0,
        oa_status="oa" if item.get("isOpenAccess") == "Y" else "",
        pdf_url=pdf_url,
        urls={"europepmc": item.get("id", "")} if item.get("id") else {},
        source="europepmc",
    )


def search(query: str, limit: int = 10) -> tuple:
    try:
        params = {"query": query, "format": "json", "resultType": "core", "pageSize": min(limit, 1000)}
        resp = http_client.get(
            "https://www.ebi.ac.uk/europepmc/webservices/rest/search", params=params
        )
        if resp.status_code != 200:
            return [], {"status": "error", "http_status": resp.status_code}
        data = resp.json()
        results = (data.get("resultList") or {}).get("result") or []
        papers = [_result_to_paper(r).to_dict() for r in results[:limit]]
        return papers, {"status": "ok", "count": len(papers)}
    except Exception as exc:
        return [], {"status": "error", "error": str(exc)}


def find_oa_pdf_by_doi(doi: str) -> tuple:
    try:
        query = f"DOI:{doi}"
        papers, status = search(query, limit=1)
        if papers and papers[0].get("pdf_url"):
            return papers[0], status
        return None, status
    except Exception as exc:
        return None, {"status": "error", "error": str(exc)}
