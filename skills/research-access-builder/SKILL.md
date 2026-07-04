---
name: research-access-builder
description: Builds and installs a self-hosted academic-paper research toolkit — a Python stdio MCP server (research-access-mcp) plus a thin companion skill (research-access) — that searches OpenAlex/Crossref/Semantic Scholar/arXiv/Europe PMC, resolves legal open-access PDFs via Unpaywall/CORE, downloads and organizes PDFs, exports BibTeX/RIS, and does best-effort Google Scholar lookups. Trigger this skill for "set up paper search", "set up research access", "build a paper MCP", "install a research/academic-papers tool", "I want to find papers / download research papers / search Google Scholar / do a literature search from Claude" when the tooling isn't installed yet. This skill BUILDS/INSTALLS the tooling — it is not the tool itself. Once installed, day-to-day paper search/download/BibTeX requests are handled by the companion `research-access` skill and its MCP tools, not this one.
---

# research-access-builder

## When to use this skill

Use this skill when the user wants to **set up** paper-search/download tooling that doesn't
exist yet on this machine — phrases like "set up paper search", "install a research access
MCP", "I want a way to find and download academic papers from Claude", "build me a Google
Scholar / literature search tool".

## When NOT to use this skill

- **Day-to-day paper search/download** once the MCP server is already installed and
  registered — that's the companion `research-access` skill and its MCP tools
  (`search_papers`, `find_open_access_pdf`, `download_pdf`, etc). Don't rebuild the tooling
  every time someone asks "find me papers on X."
- **Paywall bypass of any kind.** This toolkit only ever returns links that Unpaywall, CORE,
  arXiv, or Europe PMC report as legally open access. If asked to bypass a paywall, refuse
  and explain that only legally available content is in scope.

## Design constraint: Google Scholar has no API

There is no official Google Scholar API. This toolkit leans on free scholarly APIs
(OpenAlex, Crossref, Semantic Scholar, arXiv, Europe PMC, Unpaywall) to do the heavy
lifting, and treats Google Scholar itself as **best-effort with a human-in-the-loop
fallback**: if SerpApi isn't configured and a scrape attempt is blocked, the tool hands back
a Google Scholar search URL plus instructions for the user to open it, find what they want,
and paste back a DOI or PDF link for the other tools to take over from there.

## Build workflow

**Step 0 — scope check.** If the user's request is ambiguous about whether they want just
the MCP server, just the companion skill, or both, ask. Default to **both** if unclear.

**Step 1 — scaffold.**

```
python "C:\Claude\sarges-skills\skills\research-access-builder\scripts\scaffold.py" --target C:\Claude\research-access-mcp --skills-dir C:\Users\<user>\.claude\skills
```

`scaffold.py`:
- Copies `templates\research-access-mcp\*` into `--target`.
- Creates a venv at `--target\.venv` with Python 3.12 (falls back to any 3.10+ interpreter
  it can find).
- Runs `pip install -r requirements.txt` into that venv.
- Prints the exact `claude mcp add research-access -- <venv-python> <target>\server.py`
  registration command — run that command yourself to register the server.
- If `--skills-dir` is given, copies the companion skill template there (does not force a
  junction — some workflows want a junction from a git repo instead of a plain copy; leave
  that choice to the user/orchestrator).

**Step 2 — set environment variables.** At minimum:

| Variable | Required? |
|---|---|
| `UNPAYWALL_EMAIL` | **Yes** — Unpaywall's terms require a contact email; without it OA-PDF resolution is refused with a clear message. |
| `RESEARCH_PDF_DIR` | No (default `~/Documents/Papers`) |
| `SERPAPI_API_KEY` | No — enables better Google Scholar results (free 250/mo tier) |
| `CORE_API_KEY` | No — enables CORE as an OA-PDF fallback source |
| `SEMANTIC_SCHOLAR_API_KEY` | No — raises S2 rate limit |
| `OPENALEX_API_KEY` | No — raises OpenAlex's daily usage budget |

**Step 3 — run the slice-1 test.**

```
set UNPAYWALL_EMAIL=you@example.com
set RESEARCH_PDF_DIR=%TEMP%\research-access-test
<venv-python> C:\Claude\research-access-mcp\test_slice1.py
```

Show the full PASS/FAIL output to the user.

**Step 4 — validation checklist (acceptance criteria A1–A6):**

- **A1**: `server.py` imports cleanly in the venv (`python -c "import server"`).
- **A2**: `test_slice1.py` passes all 5 steps (search returns results; OA-PDF resolves;
  PDF downloads and verifies as a real `%PDF` file >10KB; BibTeX export is a valid
  `@article` entry; repeated search hits the cache).
- **A3**: `claude mcp add` command has been run and the server shows up in `claude mcp list`.
- **A4**: `UNPAYWALL_EMAIL` is set in the environment the MCP server actually runs under
  (not just the test shell).
- **A5**: No hardcoded credentials anywhere in the installed copy — spot check with
  `grep -riE "api_key\s*=\s*['\"]\w|@gmail\.com|@.*\.(com|org|net)" <target>` and confirm
  any hits are only in comments/docs, never live code paths.
- **A6**: Companion skill (if requested) is present and its SKILL.md accurately describes
  the installed tool's tools and env vars.

## Example invocations

1. *"Set up a research access tool so I can search and download academic papers."*
   → Ask target dir (or default `C:\Claude\research-access-mcp`), run scaffold.py with
   `--target` and `--skills-dir`, walk through env vars, run test_slice1.py, report results.

2. *"I want to find papers on CRISPR gene editing and get the PDFs — can you set that up?"*
   → Recognize the tooling isn't installed yet; run the build workflow above; once
   installed, hand off the actual CRISPR search to the newly available MCP tools /
   companion skill.

3. *"Build me a paper-search MCP but skip Google Scholar, I don't need it."*
   → Run the same scaffold; note that Google Scholar is best-effort regardless and requires
   no extra setup unless they want SerpApi — nothing to skip, but mention `SERPAPI_API_KEY`
   is optional and can be left unset.

## Reference material

See `references/sources.md` for per-source details (auth, verified rate limits, routing
role) — the same file is copied into the companion skill for at-hand reference once
installed.
