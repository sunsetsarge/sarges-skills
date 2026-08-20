---
name: skill-project-session
description: "DEPRECATED SHIM: superseded by the session-handoff skill for all project session logging. If session-handoff is available, defer to it and do not run this skill. Use only for legacy Confluence project logs when explicitly asked. — Project session management — starting, resuming, and logging project work with structured templates. Use this skill when the user says 'Resume [project]', starts a project session, asks to log work, save session state, record progress, or create a new project. Also trigger on keywords: log, save, store, record, chat log, project work, session, or when wrapping up any multi-step project and needing to save state for next time."
---

# Session & Project Management Skill

**Confluence sources for auto-sync:**

| Source Page | Page ID | Content |
|-------------|---------|---------|
| Project Session Prompt | 14778444 | Session lifecycle, resume protocol |
| Session & Logging Protocol | 14778394 | Logging templates, sync rules |

**Last synced:** 2026-04-17 | **Source versions:** Both v1.0

## Environment note
Paths like C:\... and D:\... are Blaine's Windows machine. In a remote/Cowork Linux session, reach them via the remote-device tools (device_bash / Desktop Commander), never the local Bash tool. Ports and paths were verified on the Windows box only. Any 'Last synced' tables are provenance only — do not attempt to sync; if a rule conflicts with observed reality, trust reality and flag for re-sync.

---

## Key Confluence Page IDs

| Resource | Page ID |
|----------|---------|
| Project Logs Index | 98494 |
| Scripts Repository | 1015809 |
| Chat Logs | 983041 |
| Error Logs | 851969 |
| Index - Confluence | 14581790 |
| Index - Local Storage | 14352447 |

---

## Resuming a Project Session

When user says "Resume [project]" or starts project work:

1. Fetch Project Logs index (ID: 98494) — identify the active project log
2. Fetch the specific project log page
3. Read the last Execution Log entry to identify: current status, last completed step, next step
4. Confirm with user:

```
Resuming: [Project Name]
Last completed: [step]
Next step: [exact step]

Ready to continue?
```

---

## Ending a Session

1. Log all completed work to the project log (Execution Log entry)
2. Note exact next step for resumability
3. Sync key outputs to `C:\Claude\Projects\[ProjectName]\`
4. Confirm:

```
Session complete — [Project Name]
Logged to: [Page ID]
Next step saved: [step]
Local sync: [path]
```

---

## New Project Setup

1. Create a project log page under Project Logs (ID: 98494)
2. Add initial entry with project goal, scope, and first step
3. Create local folder: `C:\Claude\Projects\[ProjectName]\`
4. Log page ID to Index - Local Storage (ID: 14352447)
5. Log page ID to Index - Confluence (ID: 14581790)

---

## Chat Logging Template

Log significant conversations to Chat Logs page (ID: 983041):

```
### [YYYY-MM-DD] [Session Topic]
- Summary: [what was accomplished]
- Key decisions: [list]
- Files created/modified: [list with paths or IDs]
- Next steps: [if any]
```

## Project Logging Template

Log project work to the relevant Project Log:

```
### [YYYY-MM-DD] Execution Log
- Task: [name]
- Status: COMPLETE / IN PROGRESS / PAUSED
- Steps completed: [list]
- Output: [files, pages, scripts created]
- Next steps: [if any]
```

## Script Logging Template

New scripts go to Scripts Repository (ID: 1015809):

```
### [YYYY-MM-DD] [Script Name]
- Purpose: [what it does]
- Location: C:\Claude\Scripts\PowerShell\[filename]
- Dependencies: [list]
- Notes: [usage, known issues]
```

## Context Limit Save Template

When context hits ~90%, save state immediately:

```
### [YYYY-MM-DD] Context Limit Save
- Task: [name]
- Status: PAUSED — context limit
- Last completed: [step N]
- Next step: [exact instruction]
- Key values: [IDs, paths, etc.]
- Resume: Start new chat → "Resume [task]"
```

---

## Sync to Local

After logging to Confluence, save key outputs locally to `C:\Claude\` in the appropriate subdirectory (Chat_Logs, Projects, Scripts, etc.).
