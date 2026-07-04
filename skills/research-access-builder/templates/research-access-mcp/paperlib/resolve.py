"""Orchestration layer: fan-out search across sources, merge/dedupe/rank, resolve DOIs,
and find legal open-access PDFs. This module implements the logic behind the MCP tools
search_papers, get_paper_by_doi, and find_open_access_pdf.
"""

import re
import time

from . import cache, config, http_client
from .models import Paper
from .sources import arxiv_src, crossref, europepmc, openalex, semantic_scholar

# Source relevance rank for merge/sort — lower is "more authoritative" for ties.
_SOURCE_RANK = {
    "openalex": 0,
    "crossref": 1,
    "europepmc": 2,
    "arxiv": 3,
    "semantic_scholar": 4,
    "google_scholar": 5,
}


def _dedupe_key(paper: dict) -> str:
    doi = Paper.normalize_doi(paper.get("doi", "") or "")
    if doi:
        return f"doi:{doi}"
    title_norm = Paper.normalize_title(paper.get("title", "") or "")
    return f"title:{title_norm}"


def _merge_paper_pair(a: dict, b: dict) -> dict:
    """Merge two paper dicts describing the same work, preferring non-empty/richer fields."""
    merged = dict(a)
    for key, val in b.items():
        if key == "urls":
            merged_urls = dict(merged.get("urls") or {})
            merged_urls.update(val or {})
            merged["urls"] = merged_urls
            continue
        if key == "authors":
            if not merged.get("authors") and val:
                merged["authors"] = val
            continue
        cur = merged.get(key)
        if cur in (None, "", 0, []) and val not in (None, "", 0, []):
            merged[key] = val
    return merged


def _merge_and_dedupe(all_papers: list) -> list:
    by_key = {}
    order = []
    for paper in all_papers:
        key = _dedupe_key(paper)
        if key in by_key:
            prev = by_key[key]
            pos = min(prev.get("_pos", 999), paper.get("_pos", 999))
            nsrc = prev.get("_nsrc", 1) + 1
            merged_pair = _merge_paper_pair(prev, paper)
            merged_pair["_pos"] = pos
            merged_pair["_nsrc"] = nsrc
            by_key[key] = merged_pair
        else:
            by_key[key] = paper
            order.append(key)
    return [by_key[k] for k in order]


def _rank_key(paper: dict):
    # Sources return relevance-ordered lists, so the paper's best position across
    # sources is the primary signal; corroboration by additional sources is a boost;
    # citation count only breaks ties. Raw citation-first ranking lets any
    # mega-cited paper (e.g. GROMACS) bury the actual best match for the query.
    pos = paper.get("_pos", 999)
    nsrc = paper.get("_nsrc", 1)
    citations = paper.get("citation_count") or 0
    return (pos - 3 * (nsrc - 1), -citations)


def search_papers(
    query: str,
    author: str = None,
    year_from: int = None,
    year_to: int = None,
    venue: str = None,
    limit: int = 10,
    sources: list = None,
) -> dict:
    """Fan out to multiple sources, merge + dedupe + rank. Returns
    {"results": [...], "source_status": {...}}."""
    full_query = query
    if author:
        full_query = f"{query} {author}"

    available_sources = {
        "openalex": lambda: openalex.search(full_query, limit=limit),
        "crossref": lambda: crossref.search(full_query, limit=limit),
        "semantic_scholar": lambda: semantic_scholar.search(full_query, limit=limit),
        "europepmc": lambda: europepmc.search(full_query, limit=limit),
        "arxiv": lambda: arxiv_src.search(full_query, limit=limit),
    }

    chosen = sources if sources else ["openalex", "crossref", "semantic_scholar", "europepmc"]

    cache_key = f"{full_query}|{author}|{year_from}|{year_to}|{venue}|{limit}|{','.join(sorted(chosen))}"
    cached = cache.get("search", cache_key)
    if cached is not None:
        cached = dict(cached)
        cached["cache_hit"] = True
        return cached

    source_status = {}
    all_papers = []
    for name in chosen:
        fn = available_sources.get(name)
        if fn is None:
            source_status[name] = {"status": "skipped", "reason": "unknown source"}
            continue
        try:
            papers, status = fn()
            source_status[name] = status
            for i, p in enumerate(papers):
                p["_pos"] = i
                p["_nsrc"] = 1
            all_papers.extend(papers)
        except Exception as exc:
            source_status[name] = {"status": "error", "error": str(exc)}

    for name in available_sources:
        if name not in chosen:
            source_status.setdefault(name, {"status": "skipped", "reason": "not requested"})

    merged = _merge_and_dedupe(all_papers)

    if year_from is not None:
        merged = [p for p in merged if not p.get("year") or p["year"] >= year_from]
    if year_to is not None:
        merged = [p for p in merged if not p.get("year") or p["year"] <= year_to]
    if venue:
        v_lower = venue.lower()
        merged = [p for p in merged if v_lower in (p.get("venue") or "").lower()]

    merged.sort(key=_rank_key)
    merged = merged[:limit]
    for p in merged:
        p.pop("_pos", None)
        p.pop("_nsrc", None)

    result = {"results": merged, "source_status": source_status, "cache_hit": False}
    cache.set("search", cache_key, result, config.CACHE_TTL_SEARCH)
    return result


def get_paper_by_doi(doi: str) -> dict:
    """Crossref primary, OpenAlex enrich. Returns a merged Paper dict (or error dict)."""
    doi_norm = Paper.normalize_doi(doi)
    cached = cache.get("doi", doi_norm)
    if cached is not None:
        cached = dict(cached)
        cached["cache_hit"] = True
        return cached

    cr_paper, cr_status = crossref.get_by_doi(doi_norm)
    oa_paper, oa_status = openalex.get_by_doi(doi_norm)

    if cr_paper is None and oa_paper is None:
        return {
            "error": "DOI not found in Crossref or OpenAlex",
            "doi": doi_norm,
            "source_status": {"crossref": cr_status, "openalex": oa_status},
        }

    if cr_paper and oa_paper:
        merged = _merge_paper_pair(cr_paper, oa_paper)
    else:
        merged = cr_paper or oa_paper

    merged["source_status"] = {"crossref": cr_status, "openalex": oa_status}
    merged["cache_hit"] = False
    cache.set("doi", doi_norm, merged, config.CACHE_TTL_DOI)
    return merged


# ---------------------------------------------------------------------------
# Open-access PDF resolution chain: Unpaywall -> CORE -> arXiv -> Europe PMC
# ---------------------------------------------------------------------------


def _unpaywall_lookup(doi: str) -> dict:
    if not config.unpaywall_configured():
        return {
            "status": "refused",
            "message": (
                "UNPAYWALL_EMAIL is not set. Unpaywall requires an email address per their "
                "API terms. Set the UNPAYWALL_EMAIL environment variable and try again."
            ),
        }
    try:
        resp = http_client.get(
            f"https://api.unpaywall.org/v2/{doi}", params={"email": config.UNPAYWALL_EMAIL}
        )
        if resp.status_code != 200:
            return {"status": "error", "http_status": resp.status_code}
        data = resp.json()
        return {"status": "ok", "data": data}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def _is_pdf_url(url: str) -> bool:
    """HEAD request to check Content-Type is application/pdf."""
    try:
        resp = http_client.head(url)
        ctype = resp.headers.get("content-type", "")
        return "application/pdf" in ctype.lower()
    except Exception:
        return False


def _extract_unpaywall_pdf(data: dict) -> dict:
    """CRITICAL (probed): best_oa_location.url_for_pdf is often null even for gold OA.
    Scan best_oa_location FIRST then ALL oa_locations for a non-null url_for_pdf; if none,
    fall back to `url` only if a HEAD request confirms Content-Type application/pdf; else
    return the landing page with pdf_available: false."""
    best = data.get("best_oa_location") or {}
    oa_locations = data.get("oa_locations") or []

    candidates = [best] + [loc for loc in oa_locations if loc]

    for loc in candidates:
        pdf_url = loc.get("url_for_pdf")
        if pdf_url:
            return {
                "pdf_url": pdf_url,
                "pdf_available": True,
                "license": loc.get("license", ""),
                "landing_page": loc.get("url", ""),
            }

    for loc in candidates:
        url = loc.get("url")
        if url and _is_pdf_url(url):
            return {
                "pdf_url": url,
                "pdf_available": True,
                "license": loc.get("license", ""),
                "landing_page": url,
            }

    landing = best.get("url") or (oa_locations[0].get("url") if oa_locations else "")
    return {
        "pdf_url": "",
        "pdf_available": False,
        "license": best.get("license", ""),
        "landing_page": landing,
    }


def _core_lookup(doi: str = "", title: str = "") -> dict:
    if not config.CORE_API_KEY:
        return {"status": "skipped", "reason": "CORE_API_KEY not set"}
    try:
        query = f'doi:"{doi}"' if doi else title
        resp = http_client.get(
            "https://api.core.ac.uk/v3/search/works",
            params={"q": query},
            headers={"Authorization": f"Bearer {config.CORE_API_KEY}"},
        )
        if resp.status_code != 200:
            return {"status": "error", "http_status": resp.status_code}
        data = resp.json()
        results = data.get("results") or []
        if not results:
            return {"status": "ok", "pdf_url": ""}
        top = results[0]
        pdf_url = top.get("downloadUrl") or (top.get("fullTextUrl") if isinstance(top.get("fullTextUrl"), str) else "") or ""
        return {
            "status": "ok",
            "pdf_url": pdf_url,
            "landing_page": top.get("sourceFulltextUrls", [""])[0] if top.get("sourceFulltextUrls") else "",
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def find_open_access_pdf(doi: str = None, title: str = None) -> dict:
    """Legal-OA chain: Unpaywall -> CORE (if key) -> arXiv (if applicable) -> Europe PMC.
    Never suggests paywall bypass. Returns pdf_available:false + landing page if nothing
    legal is found."""
    if not doi and not title:
        return {"error": "Provide at least one of doi or title"}

    chain_status = {}

    doi_norm = Paper.normalize_doi(doi) if doi else ""

    if doi_norm:
        cached = cache.get("oa_pdf", doi_norm)
        if cached is not None:
            cached = dict(cached)
            cached["cache_hit"] = True
            return cached

        uw = _unpaywall_lookup(doi_norm)
        chain_status["unpaywall"] = {"status": uw.get("status")}
        if uw.get("status") == "refused":
            return {
                "pdf_available": False,
                "pdf_url": "",
                "landing_page": f"https://doi.org/{doi_norm}",
                "message": uw.get("message"),
                "chain_status": chain_status,
            }
        if uw.get("status") == "ok":
            data = uw["data"]
            extracted = _extract_unpaywall_pdf(data)
            if extracted["pdf_available"]:
                result = {
                    "pdf_url": extracted["pdf_url"],
                    "source": "unpaywall",
                    "oa_status": data.get("oa_status", ""),
                    "license": extracted["license"],
                    "pdf_available": True,
                    "landing_page": extracted["landing_page"],
                    "chain_status": chain_status,
                    "cache_hit": False,
                }
                cache.set("oa_pdf", doi_norm, result, config.CACHE_TTL_DOI)
                return result

        core_result = _core_lookup(doi=doi_norm)
        chain_status["core"] = {"status": core_result.get("status")}
        if core_result.get("status") == "ok" and core_result.get("pdf_url"):
            result = {
                "pdf_url": core_result["pdf_url"],
                "source": "core",
                "oa_status": "oa",
                "license": "",
                "pdf_available": True,
                "landing_page": core_result.get("landing_page", ""),
                "chain_status": chain_status,
                "cache_hit": False,
            }
            cache.set("oa_pdf", doi_norm, result, config.CACHE_TTL_DOI)
            return result

        arxiv_result, arxiv_status = arxiv_src.find_by_title_or_id(title=title or "")
        chain_status["arxiv"] = arxiv_status
        if arxiv_result and arxiv_result.get("pdf_url"):
            result = {
                "pdf_url": arxiv_result["pdf_url"],
                "source": "arxiv",
                "oa_status": "oa",
                "license": "",
                "pdf_available": True,
                "landing_page": arxiv_result.get("urls", {}).get("arxiv", ""),
                "chain_status": chain_status,
                "cache_hit": False,
            }
            cache.set("oa_pdf", doi_norm, result, config.CACHE_TTL_DOI)
            return result

        epmc_result, epmc_status = europepmc.find_oa_pdf_by_doi(doi_norm)
        chain_status["europepmc"] = epmc_status
        if epmc_result and epmc_result.get("pdf_url"):
            result = {
                "pdf_url": epmc_result["pdf_url"],
                "source": "europepmc",
                "oa_status": "oa",
                "license": "",
                "pdf_available": True,
                "landing_page": epmc_result.get("urls", {}).get("europepmc", ""),
                "chain_status": chain_status,
                "cache_hit": False,
            }
            cache.set("oa_pdf", doi_norm, result, config.CACHE_TTL_DOI)
            return result

        landing = f"https://doi.org/{doi_norm}"
        if uw.get("status") == "ok":
            extracted = _extract_unpaywall_pdf(uw["data"])
            landing = extracted.get("landing_page") or landing
        result = {
            "pdf_url": "",
            "source": "",
            "oa_status": uw.get("data", {}).get("oa_status", "") if uw.get("status") == "ok" else "",
            "license": "",
            "pdf_available": False,
            "landing_page": landing,
            "message": "No legal open-access PDF found. Only the landing page is legally available.",
            "chain_status": chain_status,
        }
        cache.set("oa_pdf", doi_norm, result, config.CACHE_TTL_DOI)
        return result

    # No DOI — title-only search path (arXiv + Europe PMC only, no Unpaywall without DOI).
    arxiv_result, arxiv_status = arxiv_src.find_by_title_or_id(title=title)
    chain_status["arxiv"] = arxiv_status
    if arxiv_result and arxiv_result.get("pdf_url"):
        return {
            "pdf_url": arxiv_result["pdf_url"],
            "source": "arxiv",
            "oa_status": "oa",
            "license": "",
            "pdf_available": True,
            "landing_page": arxiv_result.get("urls", {}).get("arxiv", ""),
            "chain_status": chain_status,
        }

    epmc_papers, epmc_status = europepmc.search(title, limit=1)
    chain_status["europepmc"] = epmc_status
    if epmc_papers and epmc_papers[0].get("pdf_url"):
        p = epmc_papers[0]
        return {
            "pdf_url": p["pdf_url"],
            "source": "europepmc",
            "oa_status": "oa",
            "license": "",
            "pdf_available": True,
            "landing_page": p.get("urls", {}).get("europepmc", ""),
            "chain_status": chain_status,
        }

    return {
        "pdf_url": "",
        "source": "",
        "oa_status": "",
        "license": "",
        "pdf_available": False,
        "landing_page": "",
        "message": "No DOI provided and no match found via arXiv/Europe PMC title search.",
        "chain_status": chain_status,
    }
