# Canned session openers

These replace the two boilerplate blocks Blaine retyped 13 times in 90 days. Fill the
`<blanks>`, confirm OBJECTIVE and CONSTRAINTS with him if not supplied, then run.

## CONTEXT DUMP (dictated ramble)

Use this **before** a PLANNING SESSION or WARGAME ORDER on a new project, when the unknowns are
in Blaine's head rather than in the repo. Front-loads context in one shot instead of paying for
three correction rounds later (Karpathy's "ramble session" pattern —
`SecondBrain/reference/karpathy-prompting-2-ramble-sessions.md`).

Two intake modes, same opener:
- **Live dictation** — Claude Code's mic button or any dictation tool; aim for ~10 minutes,
  unstructured, no editing.
- **Existing recording** — a HeyPocket capture, phone-call or meeting recording, or voice-memo
  transcript Blaine already has. Paste or point at the file; no re-dictation needed.

> CONTEXT DUMP — what follows is a raw dictated ramble / recording transcript, not a spec.
> Expect speech-recognition typos, restarts, tangents, and contradictions. Do not answer it
> line by line and do not start building.
> Project: `<project>`
> Do this instead:
> 1. Reconstruct it — play back a clean, organized version of what I actually meant: objective,
>    constraints, decisions already made, and things I mentioned in passing but clearly care about.
> 2. Flag contradictions and anything I said twice with different answers — quote both.
> 3. List what is still genuinely unknown, with your recommended default for each.
> 4. Stop there and wait. The plan comes next, from the reconstruction — not from the raw dump.
>
> RAMBLE / TRANSCRIPT:
> `<paste, or path to the recording transcript>`

Then run PLANNING SESSION with the reconstruction as the OBJECTIVE, and persist the raw dump
alongside PLAN.md so a later cheap session can re-derive intent without Blaine in the loop.

## PLANNING SESSION (architect-only)

> PLANNING SESSION — top model as architect only (per CLAUDE.md tier routing).
> Project: `<project>`
> Rules:
> 1. You are the planner and judge, not the executor. Produce the plan, spec, architecture, and
>    acceptance criteria in the main loop. Delegate any execution to subagents with explicit
>    model overrides (sonnet for coding, haiku for mechanical bulk, opus only for genuinely hard
>    execution).
> 2. Interview me first: ask the minimum set of questions needed to close real unknowns, in one
>    batch, with your recommended default per question. Do not ask questions the repo, memory,
>    or Confluence already answer — check first. Do not offer `[[blank]]` knobs I can't fill;
>    pick defaults and mark them REVERSIBLE.
> 3. Inventory check before planning any new build: confirm the thing doesn't already exist in
>    sarges-skills, C:\Claude\Scripts, or the installed skill list.
> 4. Deliverable: PLAN.md in the project folder — phased, each phase with acceptance criteria
>    and an explicit "who executes" tier tag, sized so a cheaper session can run one phase
>    without the plan's author in the loop. Blaine-only items in a BLAINE GATES section.
> 5. Finish with `/session-handoff wrap` (STATE.md + Confluence mirror) without being asked.
>
> OBJECTIVE: `<what done looks like, one paragraph>`
> CONSTRAINTS: `<budget / hard rules / deadlines, if any>`

## WARGAME ORDER

> WARGAME ORDER — you are not executing this mission, you are wargaming it. A cheaper executor
> (`<executor-tier>`) runs the brief below later; your job is the route it will follow.
> Project: `<project>`
> Produce:
> 1. RECON — current ground truth (read the project folder, STATE.md, Confluence log; do not
>    trust the brief's assumptions; if the requested thing already exists, say so and stop).
> 2. ROUTE — ordered steps the executor will take, each with its acceptance check and the
>    exact command/file where applicable.
> 3. FAILURE MODES — the 3–5 most likely ways the executor goes wrong, each with a tripwire
>    the executor can self-check and the fallback.
> 4. BLAINE GATES — human-only steps, flagged L-1, L-2, … so they can be tracked in a ledger.
> 5. EXECUTOR BRIEF — a single self-contained prompt for `<executor-tier>` that forbids the
>    Agent tool (delegation-spiral rule), requires artifacts for every claimed completion, and
>    ends with `/session-handoff wrap`.
> Finish with `/session-handoff wrap` yourself so the wargame output survives the session.
>
> MISSION: `<objective, one paragraph>`
> CONSTRAINTS: `<hard rules / budget / deadline>`
