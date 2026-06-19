---
description: Pursue an objective autonomously to a verifiable finish line with safety caps (applies the `goal` skill).
argument-hint: <objective to complete autonomously>
---
Apply the `goal` skill to pursue this objective autonomously:

**$ARGUMENTS**

Mandatory sequence — do not skip step 1:

1. Restate the objective in one sentence and write a **machine-verifiable finish-line condition** (something a tool/script can check true/false). If you cannot, STOP and ask me to sharpen the objective before doing any work.
2. Pick the execution engine by work shape: Workflow (parallel branches) / /loop (until-condition) / /schedule (spans time) / inline TaskCreate (linear).
3. Encode safety caps: iteration cap, no-progress cap, budget cap, scope fence. STOP for my explicit approval on anything destructive, irreversible, money-moving, or outward-facing.
4. Route each step to the cheapest viable model; offload high-volume bounded work to the local LM Studio/Ollama queue where possible.
5. Keep a TaskCreate ledger; make every step idempotent and resumable.
6. Have a **separate verification step (not the doer)** confirm the finish-line condition before declaring done.
7. On exit, report with the verification evidence and any human gate now waiting. Never claim done without it.
