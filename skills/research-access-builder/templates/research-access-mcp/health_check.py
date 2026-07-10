#!/usr/bin/env python3
"""Fast keyless health check for research-access-mcp sources.

Run monthly or before heavy use. Designed so ANY model (or a human) can run it
and read the verdict without understanding the codebase:

    <venv-python> health_check.py           # ~30-60s, network probes only
    <venv-python> health_check.py --full    # also runs the end-to-end slice test

Exit 0 = all critical sources healthy. Exit 1 = something needs attention;
the table says what. semantic_scholar 429 keyless is EXPECTED (warn, not fail).
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
UA = "research-access-healthcheck/1.0 (mailto:{email})"

# (name, url, critical, expect) — expect is a substring that must appear in the body.
# critical=True means a FAIL here breaks the core workflow. OpenAlex and Semantic Scholar
# are ENRICHMENT/secondary: search_papers fans out and degrades to Crossref + Europe PMC,
# so their keyless 429s (2026 usage-budget model / shared-pool throttle) are WARN, not FAIL.
# The core workflow only strictly needs: Crossref (search+DOI) + Unpaywall (PDF) + arXiv + Europe PMC.
PROBES = [
    ("openalex_search", "https://api.openalex.org/works?search=test&per-page=1&mailto={email}", False, '"results"'),
    ("openalex_doi", "https://api.openalex.org/works/doi:10.7717/peerj.4375", False, '"id"'),
    ("crossref_doi", "https://api.crossref.org/works/10.7717/peerj.4375?mailto={email}", True, '"DOI"'),
    ("crossref_search", "https://api.crossref.org/works?query.bibliographic=open+access&rows=1&mailto={email}", True, '"items"'),
    ("unpaywall", "https://api.unpaywall.org/v2/10.1371/journal.pcbi.1004668?email={email}", True, '"best_oa_location"'),
    ("semantic_scholar", "https://api.semanticscholar.org/graph/v1/paper/search?query=test&limit=1&fields=title", False, '"data"'),
    ("arxiv", "http://export.arxiv.org/api/query?search_query=all:test&max_results=1", True, "<entry>"),
    ("europepmc", "https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=test&format=json&resultType=lite&pageSize=1", True, '"resultList"'),
    ("arxiv_pdf", "https://arxiv.org/pdf/1706.03762", True, None),  # HEAD, expect application/pdf
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true", help="also run test_slice1.py")
    parser.add_argument("--email", default=None, help="contact email (default: UNPAYWALL_EMAIL env)")
    args = parser.parse_args()

    try:
        sys.stdout.reconfigure(line_buffering=True)  # keep parent/child output in order
    except Exception:
        pass

    import os
    email = args.email or os.environ.get("UNPAYWALL_EMAIL")
    if not email:
        print("FAIL: set UNPAYWALL_EMAIL (or pass --email) first.")
        return 1

    rows = []
    failed_critical = False
    client = httpx.Client(headers={"User-Agent": UA.format(email=email)}, timeout=30, follow_redirects=True)
    for name, url, critical, expect in PROBES:
        url = url.format(email=email)
        t0 = time.monotonic()
        try:
            if name == "arxiv_pdf":
                r = client.head(url)
                ok = r.status_code == 200 and "pdf" in r.headers.get("content-type", "")
                note = r.headers.get("content-type", "")
            else:
                r = client.get(url)
                ok = r.status_code == 200 and (expect is None or expect in r.text)
                note = f"HTTP {r.status_code}"
                if r.status_code == 429:
                    note += " (rate limited)"
        except Exception as exc:
            ok, note = False, f"{type(exc).__name__}: {exc}"
        ms = int((time.monotonic() - t0) * 1000)
        verdict = "OK" if ok else ("WARN" if not critical else "FAIL")
        if verdict == "FAIL":
            failed_critical = True
        rows.append({"source": name, "verdict": verdict, "note": note, "ms": ms})
        time.sleep(1)  # be polite between probes

    width = max(len(r["source"]) for r in rows)
    print(f"\n{'SOURCE'.ljust(width)}  VERDICT  MS     NOTE")
    for r in rows:
        print(f"{r['source'].ljust(width)}  {r['verdict']:<7}  {str(r['ms']):<5}  {r['note']}")
    print()
    print("MACHINE_READABLE:", json.dumps(rows))

    if args.full:
        print("\n--- Running test_slice1.py (end-to-end) ---")
        sys.stdout.flush()
        proc = subprocess.run([sys.executable, str(HERE / "test_slice1.py")])
        if proc.returncode != 0:
            failed_critical = True

    if failed_critical:
        print("\nRESULT: ATTENTION NEEDED — see FAIL rows above (WARN on semantic_scholar keyless is expected).")
        return 1
    print("\nRESULT: HEALTHY (semantic_scholar WARN is expected without an API key).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
