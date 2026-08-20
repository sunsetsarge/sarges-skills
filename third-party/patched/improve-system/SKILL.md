---
name: improve-system
description: Improve Blaine's PKM/AI system so it compounds over time instead of repeating mistakes. Use when the user wants to clean up or audit their knowledge base, improve a skill after a rough session, capture a story/win/lesson they just shared, mine recent sessions for missed learnings, or fill in foundational context (brand, audience, offers). Trigger phrases: "improve system", "audit my notes", "tidy the KB", "what should we learn from this", "fix this so it doesn't happen again", "capture this lesson", "review my setup". Guiding rule: never fix the same problem more than twice — the second time, fix the system.
---

# Improve System (compound over time)

The principle: **never fix a problem more than twice.** Once might be a fluke; twice means it's time to fix the system so it never recurs. Manual prompt-tweaking is too much friction to actually do, so this skill makes improvement a single, low-effort move.

This skill has **five modes**. Pick the mode from context; if it's genuinely unclear, ask in one line.

## Mode 1 — Audit
Scan the knowledge base for **stale, conflicting, or duplicate** notes.
- Walk `knowledge/` and `projects/`. Flag notes that contradict each other, duplicate the same concept, or contain info now out of date (check `date_ingested` and any claims that drift over time).
- Propose merges, edits, or deletions. Don't delete unilaterally — list changes and confirm, then apply.
- For published notes, sync the fix to Confluence (CullyHouse) too.
- Before auditing, read the prior audit notes in the KB (search "skills inventory audit" / "skills maintenance plan") and don't re-report what they already fixed or gated.

## Mode 2 — Skill Review
Improve a **skill** based on the recent back-and-forth.
- Read the recent session where the skill underperformed. Identify what it did wrong or made the model waste time on.
- Edit the skill's SKILL.md: generalize the fix (don't overfit to one example), explain the *why* rather than adding rigid MUSTs, and remove instructions that aren't pulling weight.
- Note: where to edit depends on the skill's home. Blaine-authored skills: edit the source repo (sarges-skills/skills/ — installs are junctions/copies of it). Plugin/marketplace skills: read-only — propose edits and place a patched copy in sarges-skills/third-party/patched/, then tell Blaine to reinstall. Check CATALOG.md in the repo root for which is which.
- Before auditing, read the prior audit notes in the KB (search "skills inventory audit" / "skills maintenance plan") and don't re-report what they already fixed or gated.

## Mode 3 — Experience
Capture a **story, win, or lesson** Blaine just shared — his lived experience, which is the biggest differentiator a system can have.
- Turn it into a durable note in `knowledge/` (e.g. `knowledge/lessons/<slug>.md`) with what happened, the lesson, and how to apply it next time.
- Cross-link with `[[wikilinks]]` to the relevant frameworks/people. This is the same format `ingest-resource` uses.

## Mode 4 — Historical Review
Mine **recent Claude/Cowork sessions** for learnings that were never captured.
- Use whatever session/transcript tools the environment exposes (names vary by platform — search the tool list for "session"/"transcript"). If none exist, mine the KB's session-log and project-log pages instead, or ask Blaine to point at transcripts; don't silently skip the mode.
- Pull out anything reusable: a decision, a fix, a preference Blaine expressed, a workflow that worked. File each via Mode 3 or as a memory entry.
- Flag recurring problems (the "fixed it twice" signal) and route them to Mode 2.

## Mode 5 — Foundation
Fill in missing **foundational content** the system needs to be useful: brand, audience, offers, goals.
- Review the current setup and find the gaps (e.g. no defined target audience, no stated goals, no voice guide).
- **Interview Blaine** to fill them — ask focused questions, one or two at a time.
- Write the results into `knowledge/foundation/` (e.g. `brand.md`, `audience.md`, `offers.md`, `goals.md`) and publish to Confluence so other skills (ask-the-board, internal-focus-group) can draw on them.

## How to run

1. Determine the mode from what Blaine said. State which mode you're running in one line.
2. Do the work for that mode. Show proposed changes before applying anything destructive.
3. Summarize what changed and where (file paths / Confluence links), and note any follow-up (e.g. "reinstall the skill", "two recurring issues flagged").
