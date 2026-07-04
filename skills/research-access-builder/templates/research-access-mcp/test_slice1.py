"""Slice-1 standalone test for paperlib. No MCP client needed — imports paperlib directly.

Run with UNPAYWALL_EMAIL and RESEARCH_PDF_DIR set as environment variables, e.g.:

    set UNPAYWALL_EMAIL=you@example.com
    set RESEARCH_PDF_DIR=%TEMP%\\research-access-test
    python test_slice1.py

Steps:
  1. search_papers("ten simple rules digital data storage") returns >=1 ranked result.
  2. find_open_access_pdf(doi="10.1371/journal.pcbi.1004668") returns a pdf_url.
  3. Download that PDF; assert file exists, >10KB, starts with %PDF.
  4. export_bibtex returns a valid @article entry.
  5. Repeat the search; assert the cache was hit.

Prints PASS/FAIL per step. Exit code 0 only if all pass.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from paperlib import bibtex, cache, download, resolve  # noqa: E402
from paperlib.logging_util import read_log_tail  # noqa: E402

TEST_DOI = "10.1371/journal.pcbi.1004668"
TEST_QUERY = "ten simple rules digital data storage"

results = []


def check(name: str, condition: bool, detail: str = "") -> bool:
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}" + (f" - {detail}" if detail else ""))
    results.append(condition)
    return condition


def main() -> int:
    print("=" * 70)
    print("research-access-mcp / paperlib — Slice 1 test")
    print("=" * 70)

    if not os.environ.get("UNPAYWALL_EMAIL"):
        print("WARNING: UNPAYWALL_EMAIL not set — Unpaywall calls will be refused.")

    # --- Step 1: search_papers ---
    print("\n--- Step 1: search_papers ---")
    try:
        search_result = resolve.search_papers(TEST_QUERY, limit=10)
        n = len(search_result.get("results", []))
        print(f"  query={TEST_QUERY!r} -> {n} results")
        print(f"  source_status: {search_result.get('source_status')}")
        if n:
            top = search_result["results"][0]
            print(f"  top result: {top.get('title')!r} ({top.get('year')}) [{top.get('source')}]")
        check("Step 1: search_papers returns >=1 result", n >= 1, f"got {n}")
    except Exception as exc:
        check("Step 1: search_papers returns >=1 result", False, f"exception: {exc}")

    # --- Step 2: find_open_access_pdf ---
    print("\n--- Step 2: find_open_access_pdf ---")
    oa_result = None
    try:
        oa_result = resolve.find_open_access_pdf(doi=TEST_DOI)
        print(f"  result: {oa_result}")
        has_pdf_url = bool(oa_result.get("pdf_url"))
        check("Step 2: find_open_access_pdf returns a pdf_url", has_pdf_url,
              f"pdf_url={oa_result.get('pdf_url')!r}")
    except Exception as exc:
        check("Step 2: find_open_access_pdf returns a pdf_url", False, f"exception: {exc}")

    # --- Step 3: download the PDF ---
    print("\n--- Step 3: download_pdf ---")
    test_dir = os.environ.get("RESEARCH_PDF_DIR") or str(Path(os.environ.get("TEMP", ".")) / "research-access-test")
    try:
        dl_result = download.download_pdf(doi=TEST_DOI, dest_dir=test_dir)
        print(f"  result: {dl_result}")
        if dl_result.get("status") in ("ok", "skipped"):
            path_str = dl_result.get("path")
            path = Path(path_str) if path_str else None
            if path is None and dl_result.get("status") == "skipped":
                # find file by convention if skipped result omitted path (shouldn't happen, but be safe)
                path = None
            exists = path.exists() if path else False
            size_ok = path.stat().st_size > 10 * 1024 if exists else False
            starts_pdf = False
            if exists:
                with open(path, "rb") as f:
                    starts_pdf = f.read(5).startswith(b"%PDF")
            check("Step 3: downloaded file exists", exists, f"path={path}")
            check("Step 3: downloaded file >10KB", size_ok,
                  f"size={path.stat().st_size if exists else 'n/a'}")
            check("Step 3: downloaded file starts with %PDF", starts_pdf)
        else:
            check("Step 3: downloaded file exists", False, f"download failed: {dl_result}")
            check("Step 3: downloaded file >10KB", False)
            check("Step 3: downloaded file starts with %PDF", False)
    except Exception as exc:
        check("Step 3: downloaded file exists", False, f"exception: {exc}")
        check("Step 3: downloaded file >10KB", False)
        check("Step 3: downloaded file starts with %PDF", False)

    # --- Step 4: export_bibtex ---
    print("\n--- Step 4: export_bibtex ---")
    try:
        bib_result = bibtex.export_bibtex([TEST_DOI])
        combined = bib_result.get("combined", "")
        print(f"  bibtex:\n{combined}")
        is_valid = combined.strip().startswith("@article") and "title" in combined and "}" in combined
        check("Step 4: export_bibtex returns a valid @article entry", is_valid)
    except Exception as exc:
        check("Step 4: export_bibtex returns a valid @article entry", False, f"exception: {exc}")

    # --- Step 5: repeat search, assert cache hit ---
    print("\n--- Step 5: cache hit on repeated search ---")
    try:
        search_result_2 = resolve.search_papers(TEST_QUERY, limit=10)
        cache_hit_flag = search_result_2.get("cache_hit", False)
        print(f"  cache_hit flag on repeat call: {cache_hit_flag}")
        check("Step 5: repeated search hits cache", cache_hit_flag is True)
    except Exception as exc:
        check("Step 5: repeated search hits cache", False, f"exception: {exc}")

    print("\n" + "=" * 70)
    passed = sum(1 for r in results if r)
    total = len(results)
    print(f"RESULT: {passed}/{total} checks passed")
    print("=" * 70)

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
