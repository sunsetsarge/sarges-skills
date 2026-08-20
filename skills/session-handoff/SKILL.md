---
name: session-handoff
argument-hint: "[wrap | resume <project> | plan <project> | wargame <project> <executor-tier>]"
description: Kill the hand-carried session state that eats 40% of session openers — one command replaces the pasted resume-context block, the retyped PLANNING SESSION / WARGAME ORDER boilerplate, the "Execute Phase N of PLAN.md" ritual, and the manual "log everything to confluence" bolt-on. Use at session END when the user says "log everything to confluence", "log this session", "wrap up", "save state", or work is clearly concluding — write STATE.md + publish the Confluence session log. Use at session START when the user says "resume <project>", "continue <project>", "pick up where we left off", "execute phase N", or pastes a resume-context block — read STATE.md and re-establish context instead of making them retype it. Use "plan <project>" / "wargame <project>" when the user starts typing PLANNING SESSION or WARGAME ORDER boilerplate — load the canned template from references/OPENERS.md instead. Supersedes the unused anthropic-skills:skill-project-session pattern.
---

# /session-handoff — durable state in, durable state out

90-day transcript audit (2026-07-07): 63 of 154 sessions opened with a >800-char hand-pasted
context block; "log everything to confluence" was typed 40 times as a manual afterthought;
"Execute Phase N of PLAN.md" 18 times; the PLANNING SESSION and WARGAME ORDER preambles were
retyped 13 times combined. This skill makes the harness carry that state instead of Blaine.

**Contract:** every project that has ever had a `/session-handoff wrap` owns a `STATE.md` next to
its `PLAN.md`. Wrap writes it and mirrors it to Confluence. Resume reads it. Nothing here depends
on the model tier that wrote it — a Sonnet session can resume what a Fable session wrapped.

## Verbs

### `wrap` — end of session (also triggers on "log everything to confluence")

1. **Identify the project folder.** The directory containing the files touched this session
   (usually under `...\Claude\Projects\<Project>` or `C:\Claude\Projects\Active\<Project>`).
   Multiple projects touched → one STATE.md each; ask only if genuinely ambiguous.
2. **Write/update `STATE.md`** in the project folder using `references/STATE_TEMPLATE.md`.
   Rules:
   - Overwrite the *state* sections; **append** to the `## Session log` table (newest row first).
   - `NEXT ACTION` must be a single imperative sentence a fresh session can execute without any
     other context ("Execute Phase 2 of PLAN.md: wire OAuth callback, acceptance = login round-trip").
   - `BLAINE GATES` lists only human-only items (purchases, playtests, account approvals).
   - Convert every relative date to absolute (OneDrive folder ≠ trustworthy timeline).
   - Claims of completed work go in only if verified this session (artifact exists, test ran,
     screenshot taken). Unverified subagent claims are logged under `UNVERIFIED`, not `DONE`
     — per the standing verify-subagent-claims rule.
3. **Publish the session log to Confluence** (SD space, cloudId `ca6859aa-3e7c-4331-904d-66aecb2409bb`):
   - Find the project's existing page under **Project Logs**. Append a session entry —
     **never create a duplicate page** if one exists (append-don't-duplicate rule).
   - Confluence update = **full-body replace**: GET the full body, insert the new entry, resubmit,
     then verify the live page actually contains it. Supply a `versionMessage`.
   - Include the full current STATE.md content in the entry. This is the OneDrive data-loss
     insurance: state must survive the Projects folder vanishing.
4. **Report**: path to STATE.md, Confluence page link + version, the NEXT ACTION line verbatim,
   and open Blaine gates. Nothing else.

### `resume <project>` — start of session (also triggers on "resume X" / "execute phase N")

1. **Locate STATE.md**: check the project folder (match against the Projects directory listing and
   the memory index). No STATE.md → say so, fall back to PLAN.md + the project's Confluence log,
   and create STATE.md at the next wrap.
2. **Load state, don't re-derive it.** Read STATE.md (and PLAN.md if a phase is referenced). Do NOT
   re-explore the codebase or re-ask for context the file already answers.
3. **Inventory check before building** — the audit found 3 sessions that planned builds of skills
   that already existed. If NEXT ACTION creates something new, spend one minute confirming it
   doesn't already exist (repo, Scripts workshop, skill list) before proceeding.
4. **Echo one confirmation line** ("Resuming <project> at <phase>; next: <NEXT ACTION>. Gates
   outstanding: <gates>.") and start executing. Don't ask permission to do the NEXT ACTION —
   resuming *is* the permission. Respect tier routing: the session's top model plans and judges;
   delegate mechanical execution to cheaper subagents with explicit model overrides.
5. **Phase completion = verified completion.** Before reporting a phase done, run its acceptance
   criteria from PLAN.md. An executor's "all green" without artifacts is UNVERIFIED.

### `plan <project>` / `wargame <project> <executor-tier>` — templated openers

Load the matching template from `references/OPENERS.md`, fill in the project name and executor
tier, confirm the two blanks the template can't know (objective, constraints), and begin. This
replaces retyping the ~250-word PLANNING SESSION / WARGAME ORDER boilerplate. Both templates end
with an automatic `wrap` so the plan lands in STATE.md + Confluence without being asked.

`references/OPENERS.md` also carries a **CONTEXT DUMP** template for the case where the unknowns
live in Blaine's head, not the repo. Reach for it when he opens with a long dictated ramble, or
hands over a HeyPocket / meeting / phone-call recording transcript as project input: reconstruct
intent, surface contradictions, list open unknowns — then stop and let `plan` take it from there.
Persist the raw dump next to PLAN.md.

## Scope fences

| Adjacent thing | Boundary |
|---|---|
| `workspace-audit` | That skill detects drift across the whole workspace. This skill manages one project's live state. Audit reads STATE.md files; it never writes them. |
| `goal` | /goal owns autonomous multi-step pursuit with judge/worker split. A /goal run should still `wrap` at the end; this skill does not do autonomous looping. |
| Memory files | Memory holds durable per-project *summaries* for recall. STATE.md holds the *operational* handoff (exact next action, gates). Wrap may update the project's memory file one-line status, but MEMORY.md is never the state store. |
| `anthropic-skills:skill-project-session` | Superseded by this skill for Blaine's workflow. Do not invoke both. |

## Hard rules inherited

- Every executor prompt this skill emits must OPEN with: "You ARE the delegated executor. The
  Agent/Workflow tools are FORBIDDEN — do the work yourself in this session." (Prevents the
  nested-delegation spiral — 5+ incidents, ~240k wasted tokens.)
- Canonical state lives in **two places** (STATE.md + Confluence entry) — OneDrive has lost files.
- Never mention DigitalNC / public domain / source archives in any customer-facing copy that
  passes through a wrap summary.
- No auto-deletion of anything during wrap; state files are add/update only.
