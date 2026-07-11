# OPTIMIZATION_PLAN.md — research-access, with an Opus/Sonnet operating model

**Authored 2026-07-10 (Opus). Companion to `MAINTENANCE.md` (the runbook) — this file is the
strategy: how to analyze, optimize, and maintain the toolkit using Opus + Sonnet agents, with
a special focus on the Google Scholar integration.** Persist-to-disk per workspace operating doc.

---

## 1. Analysis — what exists, and how Claude uses it with Google Scholar

### 1a. The core pipeline (works well)
`search_papers` fans out to **OpenAlex + Crossref + Semantic Scholar + Europe PMC** (arXiv on
request), merges/dedupes by DOI/title, ranks by relevance-position + multi-source corroboration +
citation tiebreak. PDF retrieval is a **legal-only resolver chain**: Unpaywall → CORE → arXiv →
Europe PMC. Verified live: 6 ADHD PDFs downloaded this session; health check HEALTHY.

### 1b. Google Scholar — the actual current behavior (grounded in `sources/scholar_gs.py`)
**Google Scholar is NOT part of the fan-out.** It is a separate best-effort tool,
`google_scholar_search`, with a 3-tier ladder:
1. **SerpApi** (`google_scholar` engine) — only if `SERPAPI_API_KEY` is set. **Not set today.**
2. **`scholarly` + FreeProxies scrape** — only if the optional `scholarly` package is installed.
   **It is not** (commented out in requirements.txt, by design — stale + block-prone).
3. **Manual-fallback payload** — returns `{manual_url: scholar.google.com/scholar?q=…,
   instructions: "open this, paste back a DOI/PDF link"}`.

**Net: today `google_scholar_search` ALWAYS returns tier 3 — a "do it yourself" stub.** It yields
zero automated results. This is a deliberate legal/anti-block posture, not a bug — but it means the
tool currently adds little over just handing the user a URL.

### 1c. The critical insight — there are TWO Google-Scholar paths, and the skill uses the weaker one
When the user asked this session to find free copies of paywalled papers, **Claude did not use the
skill's `google_scholar_search`. It used its own harness `WebSearch`/`WebFetch`** — searched
Scholar-style, judged host legitimacy, and pulled a legal institutional copy (the AAP guideline from
`medicine.tulane.edu`) into the pipeline via `download_pdf(pdf_url=…)`. That worked; the skill's GS
tool would have returned only the manual URL.

So the real human/AI loop today is:
`Claude WebSearch → Claude judges legitimacy → download_pdf(pdf_url) → legal PDF`
…and the skill's own Scholar tool sits unused beside it. **The optimization thesis: make the skill
formalize and harden the path Claude already improvises, instead of the underpowered scrape stub.**

### 1d. Concrete weaknesses (the optimization targets)
| ID | Weakness | Evidence |
|---|---|---|
| GS-1 | GS tool is a dead stub without keys; Claude's own WebSearch is strictly better but unmanaged/uncodified. | §1b/1c |
| GS-2 | **`download_pdf` trusts ANY `pdf_url`** — no host-legitimacy check. A GS/WebSearch result could be a gray re-host (e.g. a clinic re-posting an APA PDF) and it would download silently. | This session I had to judge `frisch-ot.com` by hand. |
| GS-3 | SerpApi path sets `year=None` and `doi=""` always → GS hits can't rejoin the DOI pipeline (no dedup, no Unpaywall). | `scholar_gs.py` `_via_serpapi` |
| GS-4 | `scholarly` scrape iterates a generator with no hard timeout → **hang risk** if ever installed. | `_via_scholarly` |
| B11 | Download gives up on a 403/404 instead of trying other OA locations. | Wolraich guideline failed until hand-routed. |
| B12 | Europe PMC source emits unverified `?pdf=render` URLs that 404 on newer articles. | 3× 404 this session. |
| B13 | Batch-by-DOI prefers a bot-blocked publisher link over an available PMC copy. | Dovepress/Wiley 403/404. |
| B1 | No OpenAlex/CORE keys → OpenAlex intermittent 429, CORE disabled. | Live 429 this session. |
| B2/B3 | No MCP-protocol test; no scored ranking eval. | MAINTENANCE §4 |

---

## 2. The Opus/Sonnet operating model

**Rule (from the workspace tier-routing doc): the judge is never the doer.** Opus architects +
adjudicates; Sonnet executes; Haiku only for mechanical bulk. Applied here:

| Role | Model | Responsibilities |
|---|---|---|
| **Architect / Judge** | **Opus** (session top model) | Write the per-phase SPEC + acceptance test. Make all **legal/legitimacy guardrail calls** (which hosts are allowed, whether a copy is author-posted vs. infringing). Review Sonnet's diff, re-run its tests independently, accept/reject. Adjudicate the ranking eval. |
| **Executor** | **Sonnet** | Implement one SPEC at a time. Write code + its test. Run `health_check.py --full` + the phase's test. Report **verbatim** output. Never makes a guardrail/legitimacy call — escalates to Opus. |
| **Grind** | Haiku (optional) | Mechanical only (e.g. adding many host patterns to an allowlist from a list Opus approved). |

**Every executor (Sonnet/Haiku) prompt MUST carry these guardrails** (hard-won this project):
- Forbid the **Agent tool** (delegation-spiral lesson from skill-text-adventure).
- Forbid unscoped `taskkill`/killing `python.exe` (a subagent once killed all Python).
- Edit the **repo** copy (`…\sarges-skills\…`), never only the installed copy; then deploy.
- Name the **exact files** it may touch.
- **Legal-OA only** — never add Sci-Hub/LibGen; never weaken the guardrail.
- Return **verbatim** command/test output; claims without artifacts are rejected (subagents fabricate).

**How to launch (Blaine copy-paste, or Opus in-session):**
- Single phase → `Agent` tool, `subagent_type: general-purpose`, `model: "sonnet"`, prompt = the SPEC below + guardrails.
- Multi-phase with verify gates → a `Workflow` (pipeline: Sonnet builds → Opus-effort verify stage), only if the user opts into orchestration.

---

## 3. Optimization roadmap — each phase = Opus SPEC → Sonnet build → Opus verify

### Phase G — Google Scholar, done right (headline; do first)
The goal is to replace the dead scrape stub with the **Claude-assisted, legally-gated** path Claude
already improvises, and to close the legitimacy hole.

- **G-A. Legitimacy gate on `download_pdf` (closes GS-2 — highest priority, guardrail).**
  Opus SPEC: classify any externally-supplied `pdf_url` host into `allow` (PMC/EuropePMC,
  `*.edu`/`*.ac.*`, `*.gov`, known repositories, gold-OA publishers PLOS/Frontiers/MDPI/BMC/Cureus,
  arXiv, CORE), `gray` (ResearchGate/Academia.edu/random commercial re-hosts), `deny` (never — n/a).
  For `gray`, do NOT download silently: return `{legitimacy:"unverified", host, message}` so the
  caller (Claude) must get explicit user confirmation. Opus owns the allowlist contents.
  Sonnet builds `paperlib/legitimacy.py` + wires it into `download.py`. **Acceptance:** a `.edu`
  URL downloads; a `researchgate.net` URL returns `unverified` (no file written) until forced.
- **G-B. "Assisted Scholar" workflow, documented in the companion skill (addresses GS-1).**
  Codify the loop Claude used this session so it's repeatable and safe: (1) Claude runs harness
  `WebSearch` (Scholar-style query, pirate domains blocked), (2) passes candidate URLs through the
  G-A legitimacy gate, (3) `download_pdf(pdf_url)` for `allow`, surfaces `gray` for confirmation.
  This is a **skill/docs change** (research-access SKILL.md + MAINTENANCE), not new server code —
  Opus writes the workflow; Sonnet edits the SKILL.md and adds an example. **Acceptance:** SKILL.md
  documents the WebSearch→legitimacy→download loop with the legal-host allow/gray lists.
- **G-C. SerpApi path repair (GS-3) — only when a key is added.** Parse `year` from
  `publication_info.summary`; backfill `doi` by Crossref title-match so SerpApi hits rejoin the DOI
  pipeline (dedup + Unpaywall). **Acceptance:** with a test key, a GS result gains a DOI and dedups
  against the same paper from OpenAlex.
- **G-D. `scholarly` hang-guard (GS-4).** Wrap the generator iteration in a hard wall-clock timeout;
  on timeout return manual-fallback. **Acceptance:** simulated slow proxy → tool returns within N s.
- **G-E. Merge GS into optional fan-out.** Add `google_scholar` as an opt-in source in
  `search_papers(sources=[…])`, deduped, only when a key/scholarly is available. **Acceptance:**
  requesting the GS source with a key returns merged+deduped results; without, it's skipped cleanly.

### Phase F — download reliability (B11–B13, from first live run)
Fix 403/404 fallback (continue the OA-location list + HEAD-verify), verify EuropePMC render URLs,
rank OA locations PMC/repository-before-publisher. Each: Opus SPEC + Sonnet build + Opus verify
against the exact DOIs that failed this session (AAP guideline, Dovepress, Wiley).

### Phase K — keys (B1, Blaine's ~10 min)
OpenAlex + CORE free keys → set env vars. Not an agent task; Blaine action. Unblocks OpenAlex
budget + CORE resolver. **Acceptance:** health_check all-green incl. a CORE resolve.

### Phase E — eval + maintenance harness (B2/B3)
`test_mcp_layer.py` (spawn server, call tools via the `mcp` client) and `eval_ranking.py` (≥10 golden
query→DOI pairs, scored MRR). Opus designs the golden set + adjudicates; Sonnet builds. **Acceptance:**
MCP test exits 0 through the protocol; MRR ≥ 0.7 tracked run-to-run.

**Suggested order:** G-A (guardrail) → F (reliability, highest daily impact) → K (keys) →
G-B (assisted Scholar docs) → E (evals) → G-C/D/E (Scholar depth, only if keys added).

---

## 4. Maintenance loop (ongoing)

**Monthly cadence, judge-led:**
1. **Opus** (or any session): run `health_check.py --full`; read `MAINTENANCE.md §2` triage table.
2. Triage failures → for each, write/point to a SPEC (roadmap §3 or a new B-item).
3. Dispatch **Sonnet** executor(s) with the guardrail block (§2). One SPEC per agent.
4. **Opus verifies** each diff by re-running the test itself (never trust the agent's prose).
5. Commit + push sarges-skills; full-body-update Confluence p.80609315 with a version bump.

**Optional automation:** a `/schedule` monthly cron that runs the health check and, only if it finds
a FAIL, opens a task — never auto-edits code (writes stay judge-gated).

**Blaine's copy-paste triggers:**
- Optimize (headline): *"Read `…\research-access-builder\OPTIMIZATION_PLAN.md` and execute Phase G-A,
  then G-B. You (Opus) write the spec + verify; delegate the coding to a Sonnet agent with the §2
  guardrails. Show me verbatim test output."*
- Maintain: *"Run the research-access monthly maintenance loop from OPTIMIZATION_PLAN.md §4."*
- Reliability first: *"Execute Phase F (B11–B13) per OPTIMIZATION_PLAN.md, Opus-verify each fix."*

---

## 5. What NOT to do (guardrails on the optimization itself)
- Do not add Google Scholar as a hard dependency or a default source — it stays best-effort/opt-in.
- Do not weaken the legal-OA guardrail to raise hit-rate. The G-A gate makes the guardrail *stronger*.
- Do not let `download_pdf` fetch `gray`-host URLs without explicit user confirmation.
- Do not `pip install scholarly` into the main venv — test it in a throwaway venv only (Slice-3 rule).
- Keep `mcp>=1.27,<2` pinned. Repo copy is canonical; installed copy is disposable.
