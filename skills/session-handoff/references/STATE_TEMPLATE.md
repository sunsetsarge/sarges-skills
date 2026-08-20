# STATE.md template

Copy this structure. Overwrite state sections on each wrap; append to the session log.
Everything above the session log must fit one screen — a resume session reads this in one gulp.

```markdown
# STATE — <Project Name>

Updated: <YYYY-MM-DD> (session-handoff wrap)
Status: ACTIVE | BLOCKED | GATED | PAUSED | SHIPPED
Phase: <e.g. "Phase 2 of 4 (PLAN.md)" or "no formal plan">

## NEXT ACTION
<One imperative sentence executable by a fresh session with zero extra context.
Name the file/phase and the acceptance criterion.>

## BLAINE GATES
- [ ] <Human-only item — purchase, playtest, account approval. Absolute dates.>

## KEY PATHS & FACTS
- Plan: <path to PLAN.md / SPEC.md>
- Working dir: <path>
- Credentials/config: <path or "none">
- <Non-obvious environment facts a fresh session would otherwise rediscover the hard way.>

## DONE (verified this session)
- <Only items with an artifact: file exists, test passed, screenshot taken, page live.>

## UNVERIFIED
- <Subagent/executor claims not yet checked against artifacts. Empty is the goal.>

## DECISIONS
- <YYYY-MM-DD> <Decision + one-line why. Newest first. Prevents re-litigating.>

## Session log
| Date | Model | What happened (1 line) | Confluence ver |
|---|---|---|---|
| <YYYY-MM-DD> | <model> | <summary> | <vN> |
```

Notes:
- `UNVERIFIED` exists because executors report false greens (audit: 20+ correction turns where
  "done" claims failed manual playtest). Moving an item UNVERIFIED → DONE requires an artifact.
- `DECISIONS` prevents the same-question-twice pattern (audit: identical questions re-asked in
  separate same-day sessions).
- Keep the file under ~80 lines by pruning DONE items older than two sessions — history lives in
  the Confluence log, not here.
