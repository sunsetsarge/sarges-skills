---
name: goal
argument-hint: "<objective> with a verifiable finish line"
description: Pursue a high-level objective autonomously across many steps until a verifiable finish-line condition is met, with hard safety caps and resumable state. Use when the user invokes /goal, or says "keep going until", "work autonomously until done", "finish line", "autonomous mode", "slash goal", or hands off a multi-step objective to complete without step-by-step supervision. Maps the objective onto native primitives (Workflow, /loop, /schedule, TaskCreate, subagent model routing) and separates the judge-of-done from the doer to prevent premature victory.
---

# /goal — Autonomous Objective Pursuit

Drive a high-level objective to a **verifiable** finish line across many steps, choosing the cheapest viable model per step, under hard safety caps, with resumable state. Replaces the old APP-LL-023 dual-agent protocol — rebuilt on current Claude Code primitives. The old "two agents" idea survives as one principle: **separate the judge from the doer** (§2).

## 1. Write a verifiable finish line FIRST (non-negotiable)

A goal without a machine-checkable completion test is a wish. Before any work:
- Restate the objective in one sentence.
- Define the **stop condition** as something a tool/script can verify true/false:
  - ✅ "until `audit_store_full.py` reports ≥50 products with status=published"
  - ✅ "until `manifest.jsonl` has 200 rows with ok=true for this LCCN range"
  - ✅ "until the dedup quarantine is empty and every cluster has exactly one keeper"
  - ❌ "until the store looks good" / "make the photos organized"
- If you cannot write a verifiable condition, **STOP and ask the user to sharpen the objective.** Do not start a goal you can't prove finished.

## 2. Separate the judge from the doer (the kernel of the old dual-agent design)

The agent that decides "done" must not be the one that did the work — executors declare premature victory. Enforce completion via:
- a **verification step/subagent** that independently re-checks the stop condition after each round, or
- the **Workflow adversarial-verify pattern** (spawn skeptics prompted to REFUTE "this is done"; majority-refute = not done).

Done = the *judge* confirms the condition with evidence, never the doer asserting it.

## 3. Pick the execution engine by work shape

| Work shape | Engine |
|---|---|
| Forks into parallel branches with known structure | **Workflow** tool (fan-out/pipeline, per-agent `model:` + `budget`) |
| "Keep doing X until condition / accumulate to a target" | **/loop** (self-paced or interval) |
| Spans real time / must run while you're away | **/schedule** + CronCreate |
| Linear multi-step within one session | inline, driven by a **TaskCreate** ledger |

Always back the goal with a TaskCreate ledger so progress is visible and the run is resumable.

## 4. Safety caps (encode every time — this is where autonomy earns trust)

- **Iteration cap** — max N rounds; halt and report at N even if incomplete.
- **No-progress cap** — K consecutive rounds with no measurable progress → halt and report why.
- **Budget cap** — set a token/cost ceiling (Workflow `budget`); stop when reached.
- **Time box** — wall-clock limit for looped/scheduled goals.
- **Scope fence** — touch only declared paths/projects (e.g. only `D:\SaspanPipeline\`). Never wander into other projects.
- **HUMAN GATES — never autonomous.** Anything destructive, irreversible, money-moving, or outward-facing — publishing products, sending email, deleting originals, spending money — STOPS for explicit approval (per CLAUDE.md). A /goal run may prepare these right up to the edge, then wait.

## 5. Model tiering (cheapest viable per step)

Route via subagent `model:` fields — Haiku for triage/mechanical/verification, Sonnet for implementation, Opus/Fable only for genuine architecture or judgment. Offload high-volume bounded work (classification, extraction, dedup) to the local LM Studio/Ollama queue where possible ($0). The conductor that holds the finish line stays on a capable model; the workers go cheap.

## 6. Resumability (ADHD- and cheap-model-friendly)

Every step idempotent; state in SQLite/JSON/TaskList. A killed or interrupted /goal run must resume losslessly — re-running re-reads state and continues, never restarts from zero. Use skip-if-exists, status columns (pending/processing/done/failed), and checkpoints.

## 7. Report honestly on exit

On completion OR cap-hit, report: the finish-line condition; whether the judge confirmed it (**with the verification output**); what was done; what was skipped; and any human gate now waiting. Never claim done without the evidence. If a check failed, say so with the output.

## Domain finish-line templates

| Goal | Verifiable stop condition | Engine | Human gate |
|---|---|---|---|
| Saspan product cycle | `audit_store_full.py` clean + N new products status=draft | Workflow (enhance→create→audit pipeline) | Gate B pre-publish |
| Newspaper harvest | `manifest.jsonl` has the target pages ok=true for the LCCN/date range | /loop over date range (uses `digitalnc-harvest`) | — |
| Photo dedup | quarantine empty, every cluster one keeper, change-log written | /loop + dedup scripts | confirm before deleting originals |
| Genealogy pass | each target person has ≥1 sourced citation logged | Workflow (per-person subagents) | — |

## Invocation

`/goal <objective>` (slash command) or natural language ("work autonomously until …"). Either way, §1 first: write the verifiable finish line before doing anything.
