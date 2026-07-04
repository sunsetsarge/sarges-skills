"""research-access-mcp — stdio MCP server for academic paper search/download.

Tools are thin wrappers over paperlib. Every tool catches internally and returns a
JSON-serializable dict — none of them raise to the MCP client.
"""

from typing import Optional

from mcp.server.fastmcp import FastMCP

from paperlib import bibtex, download, resolve
from paperlib.sources import scholar_gs

mcp = FastMCP("research-access")


@mcp.tool()
def search_papers(
    query: str,
    author: Optional[str] = None,
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
    venue: Optional[str] = None,
    limit: int = 10,
    sources: Optional[list] = None,
) -> dict:
    """Search academic papers across OpenAlex, Crossref, Semantic Scholar, and Europe PMC.
    Merges + dedupes results by DOI/title and ranks by source authority and citation count.

    Args:
        query: Search text (title/keywords).
        author: Optional author name to narrow results.
        year_from: Optional minimum publication year.
        year_to: Optional maximum publication year.
        venue: Optional venue/journal substring filter.
        limit: Max number of results to return.
        sources: Optional list restricting which sources to query
            (subset of openalex, crossref, semantic_scholar, europepmc, arxiv).
    """
    try:
        return resolve.search_papers(
            query, author=author, year_from=year_from, year_to=year_to,
            venue=venue, limit=limit, sources=sources,
        )
    except Exception as exc:
        return {"error": str(exc)}


@mcp.tool()
def get_paper_by_doi(doi: str) -> dict:
    """Look up a single paper by DOI. Crossref primary, OpenAlex enrich (citation count,
    open-access status)."""
    try:
        return resolve.get_paper_by_doi(doi)
    except Exception as exc:
        return {"error": str(exc)}


@mcp.tool()
def find_open_access_pdf(doi: Optional[str] = None, title: Optional[str] = None) -> dict:
    """Find a LEGAL open-access PDF for a paper via Unpaywall -> CORE -> arXiv -> Europe PMC.
    Never suggests or performs paywall bypass. If no legal PDF exists, returns the landing
    page with pdf_available: false."""
    try:
        return resolve.find_open_access_pdf(doi=doi, title=title)
    except Exception as exc:
        return {"error": str(exc)}


@mcp.tool()
def download_pdf(
    doi: Optional[str] = None, pdf_url: Optional[str] = None, title: Optional[str] = None
) -> dict:
    """Download a paper's PDF to RESEARCH_PDF_DIR (resolving via find_open_access_pdf if
    pdf_url is not given directly). Skips if the file already exists; verifies the download
    is a real PDF (Content-Type / %PDF magic bytes)."""
    try:
        return download.download_pdf(doi=doi, pdf_url=pdf_url, title=title)
    except Exception as exc:
        return {"error": str(exc)}


@mcp.tool()
def download_batch(dois: list) -> dict:
    """Download PDFs for a list of DOIs. Per-item status; never aborts the batch on one
    failure."""
    try:
        return download.download_batch(dois)
    except Exception as exc:
        return {"error": str(exc)}


@mcp.tool()
def export_bibtex(dois: list, format: str = "bibtex") -> dict:
    """Export BibTeX (or RIS, via format='ris') entries for a list of DOIs, sourced from
    Crossref metadata."""
    try:
        return bibtex.export_bibtex(dois, fmt=format)
    except Exception as exc:
        return {"error": str(exc)}


@mcp.tool()
def google_scholar_search(query: str, limit: int = 10) -> dict:
    """Best-effort Google Scholar search. Uses SerpApi if SERPAPI_API_KEY is set, otherwise
    attempts a best-effort scrape via the optional `scholarly` package. On any block or
    failure, returns a structured manual-fallback payload with a URL to open by hand and
    instructions for pasting back a DOI/PDF link."""
    try:
        papers, status = scholar_gs.search(query, limit=limit)
        if papers:
            return {"results": papers, "status": status}
        return status
    except Exception as exc:
        return {"error": str(exc)}


if __name__ == "__main__":
    mcp.run()
