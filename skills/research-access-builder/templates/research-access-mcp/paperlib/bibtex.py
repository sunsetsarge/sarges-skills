"""BibTeX / RIS export from Crossref metadata (or a cached Paper dict as fallback)."""

import re

from . import resolve
from .models import Paper
from .sources import crossref


def _bibtex_key(item_or_paper: dict, is_raw_crossref: bool) -> str:
    if is_raw_crossref:
        authors = item_or_paper.get("author") or []
        surname = ""
        if authors:
            surname = authors[0].get("family", "") or ""
        year = ""
        for date_field in ("published-print", "published-online", "issued"):
            d = item_or_paper.get(date_field)
            if d and d.get("date-parts") and d["date-parts"][0]:
                year = str(d["date-parts"][0][0])
                break
    else:
        authors = item_or_paper.get("authors") or []
        surname = authors[0].split()[-1] if authors else ""
        year = str(item_or_paper.get("year") or "")

    surname = re.sub(r"[^A-Za-z0-9]", "", surname) or "Unknown"
    return f"{surname}{year}"


def _escape_bibtex(s: str) -> str:
    return (s or "").replace("{", "").replace("}", "")


def crossref_item_to_bibtex(item: dict) -> str:
    entry_type = "article"
    if (item.get("type") or "") in ("proceedings-article", "conference-paper"):
        entry_type = "inproceedings"
    elif (item.get("type") or "") == "book":
        entry_type = "book"

    key = _bibtex_key(item, is_raw_crossref=True)

    title_list = item.get("title") or []
    title = title_list[0] if title_list else ""

    authors_bibtex = []
    for a in item.get("author") or []:
        given = a.get("given", "")
        family = a.get("family", "")
        if family:
            authors_bibtex.append(f"{family}, {given}".strip(", "))
    author_field = " and ".join(authors_bibtex)

    year = ""
    for date_field in ("published-print", "published-online", "issued"):
        d = item.get(date_field)
        if d and d.get("date-parts") and d["date-parts"][0]:
            year = str(d["date-parts"][0][0])
            break

    container = item.get("container-title") or []
    journal = container[0] if container else ""
    doi = item.get("DOI", "")
    volume = item.get("volume", "")
    pages = item.get("page", "")

    fields = [
        ("title", _escape_bibtex(title)),
        ("author", _escape_bibtex(author_field)),
        ("year", year),
        ("journal", _escape_bibtex(journal)),
        ("volume", volume),
        ("pages", pages),
        ("doi", doi),
    ]
    field_lines = "\n".join(f"  {k} = {{{v}}}," for k, v in fields if v)

    return f"@{entry_type}{{{key},\n{field_lines}\n}}"


def paper_to_bibtex(paper: dict) -> str:
    key = _bibtex_key(paper, is_raw_crossref=False)
    author_field = " and ".join(paper.get("authors") or [])
    fields = [
        ("title", _escape_bibtex(paper.get("title", ""))),
        ("author", _escape_bibtex(author_field)),
        ("year", str(paper.get("year") or "")),
        ("journal", _escape_bibtex(paper.get("venue", ""))),
        ("doi", paper.get("doi", "")),
    ]
    field_lines = "\n".join(f"  {k} = {{{v}}}," for k, v in fields if v)
    return f"@article{{{key},\n{field_lines}\n}}"


def paper_to_ris(paper: dict) -> str:
    lines = ["TY  - JOUR"]
    for author in paper.get("authors") or []:
        lines.append(f"AU  - {author}")
    if paper.get("title"):
        lines.append(f"TI  - {paper['title']}")
    if paper.get("venue"):
        lines.append(f"JO  - {paper['venue']}")
    if paper.get("year"):
        lines.append(f"PY  - {paper['year']}")
    if paper.get("doi"):
        lines.append(f"DO  - {paper['doi']}")
    lines.append("ER  - ")
    return "\n".join(lines)


def export_bibtex(dois: list, fmt: str = "bibtex") -> dict:
    """BibTeX (or RIS) from Crossref metadata (or transformed cached Paper dict).
    Returns {"entries": {doi: text}, "combined": "...", "errors": {...}}."""
    entries = {}
    errors = {}

    for doi in dois:
        doi_norm = Paper.normalize_doi(doi)
        try:
            raw = crossref.raw_item_by_doi(doi_norm)
            if raw:
                if fmt == "ris":
                    paper = resolve.get_paper_by_doi(doi_norm)
                    entries[doi] = paper_to_ris(paper)
                else:
                    entries[doi] = crossref_item_to_bibtex(raw)
                continue

            paper = resolve.get_paper_by_doi(doi_norm)
            if "error" in paper:
                errors[doi] = paper["error"]
                continue
            entries[doi] = paper_to_ris(paper) if fmt == "ris" else paper_to_bibtex(paper)
        except Exception as exc:
            errors[doi] = str(exc)

    combined = "\n\n".join(entries.values())
    return {"entries": entries, "combined": combined, "errors": errors, "format": fmt}
