# Skills Catalog

Source-of-truth catalog for Blaine's skill ecosystem. Mirrored to Confluence (Skills Catalog page) for human browsing. This file is the canonical copy; regenerate the Confluence page from it, never the reverse.

Last updated: 2026-06-12

## sarges-skills (this repo — `C:\Claude\sarges-skills`)

| Skill | Triggers | Replaces | Version |
|---|---|---|---|
| `digitalnc-harvest` | saspan, digitalnc, chronam, chronicling america, loc.gov, iiif, vintage newspaper, ad extractor/reviewer/selector, ALTO OCR | APP-LL-024 | 1.0.0 |
| `goal` | /goal, goal, finish line, autonomous, "work until done" | APP-LL-023 | 1.0.0 |
| `anti-sycophancy` | CHALLENGE / STRESS TEST / PRE-COMMIT / STEELMAN; evaluative responses | APP-AS | 1.0.0 |
| `chatgpt-desktop` | ask chatgpt, query chatgpt, generate image via chatgpt | — | 1.0.0 |
| `browser-game-builder` | build/clone/finish a browser·HTML5·canvas game, RTS/tower-defense/top-down shooter, add units·sprites·factions·game sfx·balance, 8-dir sprite facing | — | 1.0.0 |

Slash command: `commands/goal.md` → installed at `~/.claude/commands/goal.md` (`/goal <objective>`).
Third-party installed skills are credited (not copied) in `third-party/CREDITS.md` — public repo is Option A: authored code + cited upstream links.

## anthropic-skills plugin (already installed — do NOT duplicate)

| Skill | Covers old protocol |
|---|---|
| `skill-3d-printing` | APP-LL-018 (3D printing, STL, Bambu, 25 rules) |
| `skill-comfyui` | ComfyUI Protocol |
| `skill-powershell` | APP-LL-017 Script Reuse |
| `skill-lego` | LEGO Integration |
| `skill-project-session` | Session & Logging + Project Session Prompt |
| `skill-genealogy-research-agent` | Genealogy research |
| `consolidate-memory` | Index Maintenance (monthly pass) |
| `ingest-resource` | Resource capture/filing |
| `improve-system` | Lessons-learned capture |

## Installed standalone skills (~/.claude/skills)

anti-sycophancy (APP-AS triggers), adhd-assistant, ollama-local, bambu-print, chatgpt-desktop, drawio-skill, stock-analysis, office365-connector, home-assistant-agent-secure, web-mcp, mcp-workflow, ralph, goodreads, local-places, google-web-search, windows-control, 3d-ai-studio-api, meshy-3d-generation, meshy-3d-printing, youtube-* (consolidation pending), voice-email (stub — delete), general-writing (broken — fix/delete).

## NOT skills (correct home is elsewhere)

| Old protocol | Home |
|---|---|
| Relay check (APP-LL-015) | SessionStart hook |
| File-org audit trail (APP-LL-019) | PreToolUse hook |
| Index Maintenance | Weekly scheduled task + monthly consolidate-memory |
| Anti-sycophancy defaults + footer, Versioning, Chunking, cloudId | CLAUDE.md |
| Tool Search, Context Limit, Atlassian session-start | Native — deleted |

See `Workspace Optimization\PROMPT_TREE_AUDIT.md` (Confluence 69926919) for the full mapping rationale.
