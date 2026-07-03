---
name: workspace-audit
argument-hint: "[--quick | --full] [--publish]"
description: Run the Audit-N workspace drift check on command — data-loss canary for canonical docs (OneDrive has eaten files before), skill-library junction drift vs the sarges-skills repo, MCP setup health (config + recent log errors, point-in-time), hooks/settings state, memory-index consistency, Projects-folder hygiene, Scripts-workshop growth, and (--full) Confluence bloat — then writes an Audit-N-style report (Headline findings / Component notes / Action checklist). Use when the user says "run an audit", "audit my setup", "audit my workspace", "check for drift", "workspace audit", "Audit 8" (or any Audit N), or invokes /workspace-audit. NOT a scheduled monitor (that is the separate MCP Error Log Monitor & Reporter idea) and NOT a content improver (delegate KB/skill content quality to improve-system).
---

# /workspace-audit — Audit-N Drift Check on Command

Formalizes the manual "Audit N" session pattern (Audits 1–7, Confluence SD space, parent page 66519041) into a repeatable on-command checklist. Point-in-time, **read-only**, pull-based. It detects drift and reports; it never fixes anything autonomously.

## 0. Scope fences (what this skill deliberately does NOT do)

| Adjacent thing | Boundary |
|---|---|
| **MCP Error Log Monitor & Reporter** (Ideas Tracker, 2026-04-30, backlog) | That idea = *scheduled, continuous, push* (parse logs → alert Slack/Discord/Confluence). This skill = *on-command, point-in-time, pull*. The MCP section here reads the same logs but only summarizes errors since the last audit. If the Monitor is ever built, it should reuse `scripts/collect.ps1`'s MCP section, and this skill's MCP check should switch to reading the Monitor's latest report instead of raw logs. One collector, two consumers — never two parsers. |
| **improve-system skill** | That skill improves KB/skill *content quality*. This skill detects *state drift* (what exists vs. what should). Where a check finds a quality problem, the report says "run improve-system on X" — it does not do the improvement. |
| **/goal, /schedule** | This skill is single-shot. If Blaine later wants it recurring, wrap the finished skill in /schedule — zero redesign needed. Do not build scheduling into the skill. |
| **Fixing drift** | NEVER auto-remediate. No deletions, no junction repairs, no settings edits. Output is an action checklist; each fix is a separate, human-approved step. (Consistent with the dedup/delete safety rule.) |

## 1. Run the collector first (zero-token facts)

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\Claude\sarges-skills\skills\workspace-audit\scripts\collect.ps1" -OutFile "$env:TEMP\audit_facts.json"
```

`collect.ps1` is read-only, no-network, PowerShell 5.1-compatible, and **redacts secrets** (it emits key *names* and presence booleans only — never values matching `token|key|secret|password|webhook`). It gathers raw facts; all judgment stays with the model. If the script is missing or errors, fall back to running the equivalent checks manually with individual commands — do not skip the audit.

Read the JSON, then evaluate the checks below **in this order** (scariest first, so a partial run still catches the critical stuff).

## 2. The checklist

Severity levels: **CRITICAL** (data loss / canonical thing missing), **DRIFT** (state ≠ recorded intent or baseline), **INFO** (growth/counts worth watching), **OK**.

### Check 1 — Data-loss canary (CRITICAL class)
OneDrive lost 4 canonical docs in June 2026. Verify existence AND non-trivial size (> 500 bytes) of every path in the baseline's `canonical_files` list. Seed list:
- `Projects\CLAUDE.md`
- `~\.claude\projects\...\memory\MEMORY.md` (the auto-memory index)
- `Projects\Workspace Optimization\AUDIT_*.md` (latest known)
- every `PLAN.md` / `SPEC.md` / `SHIP_SPEC.md` recorded in the baseline
Any file present at last audit and gone now → **CRITICAL**, top of Headline findings, with the instruction "check OneDrive online version history / recycle bin NOW (30-day retention)."

### Check 2 — CLAUDE.md, settings, hooks
- `Projects\CLAUDE.md` parses sanely (has the directory map, hard rules, model-tiering sections).
- `~\.claude\settings.json`: does a `hooks` block exist? (Audit 7: hooks were never wired — if still absent, this stays a standing DRIFT item.)
- `settings.local.json`: stale one-off allowlists → DRIFT (Audit 7 flagged the Gmail-purge leftover).

### Check 3 — Skill library drift
Compare three sources: `~\.claude\skills\` entries (with junction targets), `C:\Claude\sarges-skills\skills\` (the repo), and the baseline.
- Authored skill in the repo but junctioned from elsewhere (e.g. `.agents`) or a loose unversioned dir → DRIFT.
- Repo skill not installed at all → DRIFT.
- Known-overlap families (e.g. 5 YouTube skills → keep 2, per Audit 7) still unpruned → DRIFT.
- Skills added/removed since baseline → INFO (list them).
- Repo git state: uncommitted changes or unpushed commits → INFO.

### Check 4 — MCP setup health (point-in-time)
- Enumerate configured servers: Claude Code (`~\.claude.json` mcpServers + any project `.mcp.json`) and Claude Desktop (`%APPDATA%\Claude\claude_desktop_config.json`).
- Servers configured but dead-on-arrival (log shows connection failure) → DRIFT.
- Error counts per server from logs **since the last audit date only** (Claude Desktop: `%APPDATA%\Claude\logs\mcp*.log`; Claude Code: paths as discovered by collect.ps1). Top-3 noisiest servers → INFO with counts.
- Do NOT page through months of logs; this is a summary, not the Monitor.

### Check 5 — Memory-index consistency
- Every file in the memory dir has a MEMORY.md pointer line, and vice versa → mismatches are DRIFT.
- Sample 5 memories for stale disk-pointers (paths they reference that no longer exist) → DRIFT per stale pointer. Full sweep only on `--full`.

### Check 6 — Projects workspace hygiene
- Empty folders (no files) → INFO, listed for delete-or-README.
- Active-project folders (touched < 30 days) missing a PLAN/SPEC/README → INFO.

### Check 7 — Scripts workshop growth
- File count in `C:\Claude\Scripts` vs. baseline → INFO with delta (432 → 6,273 between Audits 3 and 7; unindexed growth is the failure mode).
- `SCRIPTS_INDEX.md` exists and is newer than the newest script? If not → DRIFT.

### Check 8 — Confluence bloat (`--full` only; needs network)
- Pages modified in SD since last audit (count only).
- Duplicate-title candidates (CQL title search on new pages vs. existing) → DRIFT per the append-don't-duplicate rule.
- Skip silently if Atlassian MCP is unavailable; say so in the report.

## 3. Baseline and audit numbering

- Baseline lives at `~\.claude\audit\baseline.json` — **not** in OneDrive (loss risk) and **not** in the sarges-skills repo (repo is public; machine state stays private). Structure: `{ last_audit_n, last_audit_date, canonical_files[], skills{}, mcp_servers[], scripts_count, notes }`.
- First run: no baseline → run everything, report what's checkable without one, then **write the baseline** (the one state-mutating step, and it only touches `~\.claude\audit\`).
- Subsequent runs: read baseline → diff → report → update baseline **only after the report is written**.
- Audit number: `last_audit_n + 1` (series is at 7 as of 2026-07-01; next is Audit 8).

## 4. Report format (match the existing Audit-N pages exactly)

Title: `Audit N — Workspace Drift Check (YYYY-MM-DD)` (or a sharper theme if one finding dominates).

```markdown
# Audit N — <title>
**Date:** YYYY-MM-DD · **Companion to:** Workspace Optimization Strategy (66519041) and Audits 1–(N-1) · **Local copy:** Projects\Workspace Optimization\AUDIT_RUNS\AUDIT_N_YYYY-MM-DD.md · **Mode:** quick|full

## 1. Headline findings
1. **<CRITICAL/DRIFT items, numbered, bolded lead>** — one line each, worst first.

## 2. Component notes
* **<area>:** <verdict + one-line evidence> — one bullet per check (1–8), including the OKs.

## 3. Action checklist
| # | Action | When |
|---|---|---|
| 1 | <fix> | TODAY / this week / next / low priority |
```

Rules: every check appears in §2 even when OK (an audit that only lists problems can't prove it looked). Every CRITICAL/DRIFT in §1 gets a row in §3. No auto-fixes.

## 5. Output routing

1. Always: write the report to `Projects\Workspace Optimization\AUDIT_RUNS\AUDIT_N_YYYY-MM-DD.md`.
2. `--publish` (or when the user confirms): create it as a **child of page 66519041** in Confluence SD, continuing the Audit-N series — never a duplicate top-level page. Include a `versionMessage` if updating.
3. Update `~\.claude\audit\baseline.json` last.

## 6. Model routing (post-Fable friendly)

The whole audit is designed to run on **Sonnet or Opus** with no Fable in the loop: collect.ps1 does the enumeration for free; the model only diffs, judges severity, and writes the report. If a check unexpectedly needs bulk file reading (e.g. sampling memories, log triage), delegate that to a `haiku` subagent or the `gemini-analyzer` agent — the orchestrator never grinds through file lists itself.

## 7. `--quick` vs `--full`

- `--quick` (default): Checks 1–7, memory sampling capped at 5, MCP logs since last audit only. Target: under ~5 minutes.
- `--full`: adds Check 8 (Confluence), full memory-pointer sweep, and per-skill description-overlap review (recommend improve-system where warranted).
