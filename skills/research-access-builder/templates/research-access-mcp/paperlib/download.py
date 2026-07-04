"""PDF download logic: filename construction, download, verification, batch handling."""

import re
from pathlib import Path

from . import config, http_client, resolve
from .logging_util import log_operation
from .models import Paper


def _ascii_safe(s: str) -> str:
    s = s.encode("ascii", "ignore").decode("ascii")
    return s


_WINDOWS_ILLEGAL = r'<>:"/\\|?*'


def _strip_illegal(s: str) -> str:
    return re.sub(f"[{re.escape(_WINDOWS_ILLEGAL)}]", "", s)


def _first_author_surname(authors: list) -> str:
    if not authors:
        return "Unknown"
    first = authors[0].strip()
    parts = first.split()
    if not parts:
        return "Unknown"
    # Heuristic: if the name has a comma ("Smith, John"), surname is before the comma.
    if "," in first:
        surname = first.split(",")[0].strip()
    else:
        surname = parts[-1]
    surname = _strip_illegal(_ascii_safe(surname))
    return surname or "Unknown"


def _short_title(title: str, max_len: int = 40) -> str:
    t = _strip_illegal(_ascii_safe(title or "Untitled"))
    t = re.sub(r"\s+", "_", t.strip())
    t = t[:max_len].rstrip("_")
    return t or "Untitled"


def build_filename(paper: dict) -> str:
    year = paper.get("year") or "n.d."
    author = _first_author_surname(paper.get("authors") or [])
    title = _short_title(paper.get("title") or "")
    return f"{author}{year}_{title}.pdf"


def _verify_pdf(path: Path) -> bool:
    try:
        if path.stat().st_size < 100:
            return False
        with open(path, "rb") as f:
            header = f.read(5)
        return header.startswith(b"%PDF")
    except Exception:
        return False


def download_pdf(doi: str = None, pdf_url: str = None, title: str = None, dest_dir: str = None) -> dict:
    """Resolve if needed, download to RESEARCH_PDF_DIR (or dest_dir override), verify,
    skip-if-exists. Never raises to caller."""
    config.ensure_dirs()
    out_dir = Path(dest_dir) if dest_dir else config.RESEARCH_PDF_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    paper_meta = {"title": title or "", "authors": [], "year": None}
    resolved_source = ""

    try:
        if not pdf_url:
            oa = resolve.find_open_access_pdf(doi=doi, title=title)
            if not oa.get("pdf_available"):
                log_operation(
                    "download_pdf", doi=doi, title=title, status="no_pdf_available",
                    message=oa.get("message", ""),
                )
                return {
                    "status": "failed",
                    "reason": "no_open_access_pdf_found",
                    "detail": oa,
                }
            pdf_url = oa["pdf_url"]
            resolved_source = oa.get("source", "")

        if doi:
            paper_lookup = resolve.get_paper_by_doi(doi)
            if "error" not in paper_lookup:
                paper_meta = paper_lookup

        if not paper_meta.get("title") and title:
            paper_meta["title"] = title

        filename = build_filename(paper_meta)
        dest_path = out_dir / filename

        if dest_path.exists():
            log_operation("download_pdf", doi=doi, pdf_url=pdf_url, status="skipped_exists",
                           path=str(dest_path))
            return {
                "status": "skipped",
                "reason": "file_already_exists",
                "path": str(dest_path),
            }

        resp = http_client.get(pdf_url)
        if resp.status_code != 200:
            log_operation("download_pdf", doi=doi, pdf_url=pdf_url, status="http_error",
                           http_status=resp.status_code)
            return {"status": "failed", "reason": f"http_{resp.status_code}", "pdf_url": pdf_url}

        content_type = resp.headers.get("content-type", "")
        body = resp.content

        if "application/pdf" not in content_type.lower() and not body[:5].startswith(b"%PDF"):
            log_operation("download_pdf", doi=doi, pdf_url=pdf_url, status="not_a_pdf",
                           content_type=content_type)
            return {
                "status": "failed",
                "reason": "response_not_a_pdf",
                "content_type": content_type,
                "pdf_url": pdf_url,
            }

        dest_path.write_bytes(body)

        if not _verify_pdf(dest_path):
            dest_path.unlink(missing_ok=True)
            log_operation("download_pdf", doi=doi, pdf_url=pdf_url, status="verify_failed")
            return {"status": "failed", "reason": "downloaded_file_failed_verification"}

        log_operation("download_pdf", doi=doi, pdf_url=pdf_url, status="ok",
                       path=str(dest_path), source=resolved_source)
        return {
            "status": "ok",
            "path": str(dest_path),
            "size_bytes": dest_path.stat().st_size,
            "source": resolved_source,
        }

    except Exception as exc:
        log_operation("download_pdf", doi=doi, pdf_url=pdf_url, status="exception", error=str(exc))
        return {"status": "failed", "reason": "exception", "error": str(exc)}


def download_batch(dois: list) -> dict:
    """Loop download_pdf across a list of DOIs. Never aborts the batch on one failure."""
    results = {}
    for doi in dois:
        try:
            results[doi] = download_pdf(doi=doi)
        except Exception as exc:
            results[doi] = {"status": "failed", "reason": "exception", "error": str(exc)}
    summary = {
        "total": len(dois),
        "ok": sum(1 for r in results.values() if r.get("status") == "ok"),
        "skipped": sum(1 for r in results.values() if r.get("status") == "skipped"),
        "failed": sum(1 for r in results.values() if r.get("status") == "failed"),
    }
    return {"results": results, "summary": summary}
