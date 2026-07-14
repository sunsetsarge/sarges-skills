# MAINTENANCE.md — research-access toolkit runbook

**Audience:** any later Claude session (Opus/Sonnet/Haiku) or Blaine himself. This file is
self-contained — you do not need the original build conversation. Written 2026-07-07 after
the first real install. Judge/executor split per Blaine's tier-routing rule: the session's
top model plans and judges; Sonnet executes; Haiku grinds.

## 1. Map of the system

| Thing | Location |
|---|---|
| Builder skill (canonical, git) | `C:\Claude\sarges-skills\skills\research-access-builder\` → github `sunsetsarge/sarges-skills` |
| Installed MCP server (live) | `C:\Claude\research-access-mcp\` (venv at `.venv\`, currently Python 3.10.6 from `C:\AI-Shared\python.exe` because the machine's 3.12 is broken — missing python312.dll) |
| MCP registration | user scope in `C:\Users\blain\.claude.json` — `claude mcp list` should show `research-access ✓` |
| Companion usage skill | `C:\Users\blain\.claude\skills\research-access\` (plain copy, NOT a junction) |
| Env vars (User level) | `UNPAYWALL_EMAIL=blaine.cully@gmail.com` (required), `RESEARCH_PDF_DIR=D:\Documents\Papers`. Optional/unset: `OPENALEX_API_KEY`, `SEMANTIC_SCHOLAR_API_KEY`, `CORE_API_KEY`, `SERPAPI_API_KEY` |
| Runtime cache / logs | `%LOCALAPPDATA%\research-access\cache.db` (SQLite) and `log.jsonl` |
| Spec + acceptance record | `Projects\Research_Access_Builder\PLAN.md` |
| Confluence log (canonical copy) | SD space, page **80609315** under Project Logs |
| API facts + verified limits | `references/sources.md` (in this dir; copy inside companion skill) |

**Golden rule of edits:** the REPO copy is canonical. Edit templates here → test → copy to
the installed dir (or re-run scaffold) → commit/push → bump the Confluence page. Never edit
`C:\Claude\research-access-mcp\` alone; it will be overwritten by the next scaffold.

## 2. Health-check protocol (run monthly, or before heavy use, or when a tool misbehaves)

```powershell
$env:UNPAYWALL_EMAIL='blaine.cully@gmail.com'
& C:\Claude\research-access-mcp\.venv\Scripts\python.exe C:\Claude\research-access-mcp\health_check.py --full
```

Reading the output:
- **All OK / exit 0** → healthy, stop.
- **semantic_scholar WARN (429)** → EXPECTED keyless; ignore unless a key is configured.
- **openalex FAIL** → likely the 2026 usage-budget model tightening. Check
  https://developers.openalex.org/guides/authentication. Mitigation: get a free key
  (openalex.org/settings/api) and set `OPENALEX_API_KEY`; search auto-falls-back to Crossref meanwhile.
- **unpaywall FAIL** → check `UNPAYWALL_EMAIL` is set in the env the server runs under; then
  check help.openalex.org for endpoint changes (Unpaywall runs on OpenAlex infra since May 2025).
- **crossref FAIL** → check X-Rate-Limit headers and the Dec-2025 polite-pool rules; verify UA string intact.
- **arxiv FAIL/429** → they tightened limits Feb 2026; raise the inter-request delay in `paperlib/sources/arxiv_src.py`.
- **Schema drift** (probe OK but tools return empty fields) → run the failing source module directly, diff
  actual JSON against the field names in `paperlib/sources/<name>.py`, patch defensively (`.get()` chains).

## 3. How to execute an improvement (protocol for ANY model)

1. **Recon (cheap):** read this file, `PLAN.md`, `references/sources.md`. Run the health check. Do NOT re-derive the API landscape from training data — it drifted in 2026 and the verified facts are in sources.md.
2. **Pick work:** from the backlog below (top-down), or the health-check failure.
3. **Edit in the repo** (`templates/research-access-mcp/...`), never only in the installed copy.
4. **Test:** `test_slice1.py` must stay 7/7; add a check to it (or `health_check.py`) covering your change. Test with the installed venv python.
5. **Deploy:** copy changed files to `C:\Claude\research-access-mcp\` (or re-run scaffold.py — it is idempotent, `dirs_exist_ok`), then restart any live Claude session using the MCP.
6. **Record:** commit+push sarges-skills; update Confluence page 80609315 (full-body replace — GET body, edit, resubmit with versionMessage; there is no append API); bump the version table.
7. **Verify like you don't trust yourself:** paste verbatim test output in your report. Claims without artifacts get rejected (standing rule: subagents have fabricated findings before).

**If delegating to a subagent, the executor prompt MUST:** forbid the Agent tool (delegation-spiral lesson), forbid unscoped `taskkill`/killing python.exe, require verbatim command output in the final report, and name the exact files it may touch.

## 4. Improvement backlog (priority order, each with acceptance test)

| # | Item | Why | Acceptance |
|---|---|---|---|
| B1 | **Get free API keys** (Blaine, ~10 min): OpenAlex key at openalex.org/settings/api; CORE key at core.ac.uk/services/api. Set `OPENALEX_API_KEY`/`CORE_API_KEY` user env vars. (S2 key: form at semanticscholar.org/product/api — may be refused for gmail addresses; skip if so.) | Raises OpenAlex daily budget ~10x; turns CORE on as a second OA-PDF resolver | health_check shows all OK; `find_open_access_pdf` chain_status includes `core: ok` |
| B2 | **MCP-layer E2E test**: current tests import paperlib directly; nothing exercises the FastMCP tool wrappers. Add `test_mcp_layer.py` that spawns server.py as a subprocess and calls tools via the `mcp` client library. | The tool JSON schemas / wrapper bugs are currently untested | script exits 0, exercises search_papers + download_pdf through the MCP protocol |
| B3 | **Ranking eval harness**: `eval_ranking.py` with ~10 golden queries (known target DOI each); score = MRR. Current ranking (per-source position + multi-source boost + citation tiebreak) was validated on ONE query. | Prevents ranking regressions; one anecdote is not an eval | MRR ≥ 0.7 on the golden set, tracked run-to-run in the log |
| B4 | **Slice 3 real-path test**: `pip install scholarly` into a THROWAWAY venv, test `google_scholar_search` with FreeProxies, document real block behavior in sources.md. Do not add scholarly to the main venv (stale pkg, hangs possible). | Fallback branch is tested; the live branch never has been | documented outcome in sources.md (works / blocked / hangs), fallback still intact |
| B5 | **Filename collision handling** in download.py: two papers by same first author + year overwrite risk (`Smith2020_...` truncated titles can collide). Add `-2` suffix on hash mismatch. | Data-loss class bug | unit check: two distinct fake papers → two files |
| B6 | **Honor Retry-After / X-Rate-Limit headers** in http_client.py backoff (Crossref sends them; currently only exponential+jitter). | Politeness + fewer failures | on stubbed 429 with Retry-After: 3, waited ≥3s |
| B7 | **Abstract quality**: verify OpenAlex `abstract_inverted_index` reconstruction produces readable text; S2/Crossref abstracts as fallback. | Abstracts feed literature-review use | search result for a known paper contains ≥200 chars of readable abstract |
| B8 | **skill-creator eval loop** on both skills (same pending status as other 2026-07-04 skills). | Description-trigger accuracy | eval report ≥ threshold in sarges-skills conventions |
| B9 | **Repair Python 3.12** (already chipped as a separate task) then rebuild venv with 3.12. | 3.10 fallback works but is EOL Oct 2026 | `py -3.12 --version` OK; venv rebuilt; tests 7/7 |
| B10 | **Zotero/Obsidian export hook**: push downloaded papers + BibTeX into the SecondBrain vault pipeline. | Ties into existing knowledge-base flow | downloaded paper appears as vault note with citation |

### Field findings — first live run, 2026-07-07 (ADHD query, 5 PDFs delivered)

Real bugs surfaced downloading real papers. All three reduce hit-rate on genuinely-OA papers; none are guardrail violations. Fix with the §3 protocol (edit repo, add a test, deploy, verify).

| # | Bug | Repro | Fix direction | Acceptance |
|---|---|---|---|---|
| **B11** | **No fallback when a resolved `pdf_url` 403s/404s.** `download_pdf` uses the first URL (search-provided or Unpaywall's) and gives up on HTTP error instead of trying the rest of the chain. | AAP guideline `10.1542/peds.2011-2654` (gold/bronze OA) → Unpaywall returns the publisher URL that 403s → download fails though OA copies may exist. | On non-200 (esp. 403/404), continue the Unpaywall `oa_locations` list, then CORE/arXiv/EuropePMC, HEAD-verifying each, before returning failure. | The AAP DOI either downloads a real %PDF or reports `pdf_available:false` only after all locations tried (chain_status shows >1 attempt). |
| **B12** | **Unverified EuropePMC `?pdf=render` URLs.** The europepmc source sets `pdf_url` to `europepmc.org/articles/PMC…?pdf=render` without checking it resolves; works for older PMC items (PMC7330190 ✓) but 404s for many 2026 ones (PMC13253956, PMC5505611, PMC13240010 ✗). | Any recent EuropePMC-only result — the render URL 404s on download. | HEAD-verify the render URL in the source module; if not a PDF, fall back to `fullTextUrlList` OA entry or leave `pdf_url` empty so the resolver keeps looking. | A result's `pdf_url`, when non-empty, HEAD-returns `application/pdf`. |
| **B13** | **Batch-by-DOI prefers a bot-blocked publisher link over a working PMC copy.** Re-resolving a DOI grabs Unpaywall's publisher `url_for_pdf` (Dovepress/Wiley/SAGE) that 403/404s, when a PMC full-text exists. | `10.2147/ndt.s130444` → Dovepress 404; `10.1002/gps3.70030` → Wiley 403 — both have PMC copies. | Rank `oa_locations` by host friendliness (PMC/repository before publisher) and/or fall through on failure (see B11). | Both DOIs download a real %PDF via the PMC/repository location. |

Practical note for operators until fixed: gold-OA publishers that serve clean PDFs to this toolkit today = **PLOS, Frontiers, Cureus, MDPI, BMC**. Bot-blockers = **Wiley, Dovepress, SAGE, AAP, APA/PsycNet, Cambridge, Elsevier(gold, no PDF link)**. When a wanted paper is on a blocker, hand `download_pdf` an explicit PMC/repository `pdf_url`, or fetch the landing page.

Reinforcing data (2026-07, RSD download run — 8/9 failed by DOI, all genuinely OA): resolving a **PLoS/PMC** DOI tends to pick `pmc.ncbi.nlm.nih.gov/articles/PMC…/pdf/….pdf`, which now returns an **HTML interstitial**, not a PDF (`reason: response_not_a_pdf`) — a very common failure since PLoS/PMC is the single most frequent OA source. **Workaround that reliably works for PLoS:** pass `https://journals.plos.org/<journal>/article/file?id=<DOI>&type=printable`. OSF preprint `…/download` and bare `doi.org` links also return HTML. **OSF/PsyArXiv preprint rule (verified 2026-07):** `api.osf.io` is bot-blocked (403 to all automated clients) and the `<guid>_v1` versioned landing serves HTML, but `https://osf.io/<BASE-guid>/download/` (base guid, no `_v1`, trailing slash) redirects to the real PDF — this retrieved both Slinn `yscdb` and, via file-GUID `osf.io/download/<fileid>/`, Alfonzo `vjqcr`. Add OSF-preprint DOIs (`10.31234/*`, `10.17605/*`) to resolver as a dedicated arm using the base-guid download path. This strengthens B11 (fallback on non-PDF content-type, not just HTTP error) and B13 (host-ranking must deprioritize `pmc.ncbi.nlm.nih.gov` PDF path in favor of the native gold-OA publisher PDF or `europepmc.org` fulltext). B11's acceptance test should assert `Content-Type: application/pdf` AND `%PDF` magic before success — the current code already checks magic (good) but does not then fall through to the next location.

## 5. Hard rules (do not violate, ever)

- **Legal OA only.** Unpaywall→CORE→arXiv→EuropePMC. No Sci-Hub, no paywall bypass, no credential sharing. If no legal PDF: return landing page and say so.
- **No hardcoded credentials/emails** in any committed file — env vars only. Grep before commit.
- **Pin `mcp>=1.27,<2`** — v2 on PyPI breaks the FastMCP import pattern.
- Google Scholar stays **best-effort with human-in-the-loop fallback** — never make it a hard dependency.
- Canonical docs live in git + Confluence, not only OneDrive (OneDrive has eaten files).

## 6. Blaine's one-page quick reference

- **Use it:** just ask Claude — "find papers on X", "get the PDF for DOI Y", "bibtex for Z". The `research-access` skill + MCP tools handle it. PDFs land in `D:\Documents\Papers`.
- **Check it:** paste into any Claude session → *"Run the research-access health check and triage any failures per MAINTENANCE.md."*
- **Improve it:** paste → *"Read C:\Claude\sarges-skills\skills\research-access-builder\MAINTENANCE.md and execute backlog item B<n> following the section-3 protocol. Delegate coding to Sonnet; report with verbatim test output."*
- **Reinstall / new machine:** *"Use the research-access-builder skill to set up paper search."*
