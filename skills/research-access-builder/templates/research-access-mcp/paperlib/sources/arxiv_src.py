"""arXiv source adapter.

Verified 2026-07-04: GET http://export.arxiv.org/api/query?search_query=...&start=0&max_results=N
returns Atom XML (parsed with stdlib xml.etree, no extra dependency). Prefixes ti:/au:/abs:/all:,
max 2000/call. Etiquette: >=3s between requests AND exponential backoff on 429 (limits were
tightened Feb 2026 — 429s happen even at 3s spacing). PDF: https://arxiv.org/pdf/{id}
(probed: 200, application/pdf, extensionless form).
"""

import time
import xml.etree.ElementTree as ET

from .. import http_client
from ..models import Paper

_ATOM_NS = "{http://www.w3.org/2005/Atom}"
_ARXIV_NS = "{http://arxiv.org/schemas/atom}"

_MAX_SOFT_RETRIES = 2


def _entry_to_paper(entry) -> Paper:
    title_el = entry.find(f"{_ATOM_NS}title")
    title = (title_el.text or "").strip().replace("\n", " ") if title_el is not None else ""

    summary_el = entry.find(f"{_ATOM_NS}summary")
    abstract = (summary_el.text or "").strip().replace("\n", " ") if summary_el is not None else ""

    authors = []
    for author_el in entry.findall(f"{_ATOM_NS}author"):
        name_el = author_el.find(f"{_ATOM_NS}name")
        if name_el is not None and name_el.text:
            authors.append(name_el.text.strip())

    published_el = entry.find(f"{_ATOM_NS}published")
    year = None
    if published_el is not None and published_el.text:
        try:
            year = int(published_el.text[:4])
        except ValueError:
            pass

    id_el = entry.find(f"{_ATOM_NS}id")
    arxiv_id = ""
    pdf_url = ""
    if id_el is not None and id_el.text:
        arxiv_url = id_el.text.strip()
        arxiv_id = arxiv_url.rstrip("/").split("/")[-1]
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}"

    doi = ""
    doi_el = entry.find(f"{_ARXIV_NS}doi")
    if doi_el is not None and doi_el.text:
        doi = Paper.normalize_doi(doi_el.text)

    return Paper(
        title=title,
        authors=authors,
        year=year,
        venue="arXiv",
        abstract=abstract,
        doi=doi,
        citation_count=0,
        oa_status="oa",
        pdf_url=pdf_url,
        urls={"arxiv": id_el.text.strip()} if id_el is not None and id_el.text else {},
        source="arxiv",
    )


def search(query: str, limit: int = 10, field_prefix: str = "all") -> tuple:
    search_query = f"{field_prefix}:{query}"
    params = {"search_query": search_query, "start": 0, "max_results": min(limit, 2000)}

    last_error = None
    for attempt in range(_MAX_SOFT_RETRIES + 1):
        try:
            resp = http_client.get(
                "http://export.arxiv.org/api/query", params=params, max_retries=0
            )
            if resp.status_code == 429:
                last_error = "429"
                if attempt < _MAX_SOFT_RETRIES:
                    time.sleep(3.0 * (attempt + 1))
                    continue
                return [], {"status": "rate_limited", "http_status": 429}
            if resp.status_code != 200:
                return [], {"status": "error", "http_status": resp.status_code}
            root = ET.fromstring(resp.text)
            entries = root.findall(f"{_ATOM_NS}entry")
            papers = [_entry_to_paper(e).to_dict() for e in entries[:limit]]
            return papers, {"status": "ok", "count": len(papers)}
        except Exception as exc:
            last_error = str(exc)
            if attempt < _MAX_SOFT_RETRIES:
                time.sleep(3.0)
                continue
            return [], {"status": "error", "error": last_error}
    return [], {"status": "error", "error": str(last_error)}


def find_by_title_or_id(title: str = "", arxiv_id: str = "") -> tuple:
    """Best-effort: search arXiv by title and return the top match, or fetch by explicit id."""
    if arxiv_id:
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}"
        return {"pdf_url": pdf_url, "arxiv_id": arxiv_id}, {"status": "ok"}
    if title:
        papers, status = search(title, limit=1, field_prefix="ti")
        if papers:
            return papers[0], status
        return None, status
    return None, {"status": "skipped", "reason": "no title or id provided"}
