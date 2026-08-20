# Skills Catalog

Source-of-truth catalog for Blaine's skill ecosystem. Mirrored to Confluence (Skills Catalog page) for human browsing. This file is the canonical copy; regenerate the Confluence page from it, never the reverse.

Last updated: 2026-08-11

## sarges-skills (this repo — `C:\Claude\sarges-skills`)

| Skill | Triggers | Replaces | Version |
|---|---|---|---|
| `digitalnc-harvest` | saspan, digitalnc, chronam, chronicling america, loc.gov, iiif, vintage newspaper, ad extractor/reviewer/selector, ALTO OCR | APP-LL-024 | 1.0.0 |
| `goal` | /goal, goal, finish line, autonomous, "work until done" | APP-LL-023 | 1.0.0 |
| `anti-sycophancy` | CHALLENGE / STRESS TEST / PRE-COMMIT / STEELMAN; evaluative responses | APP-AS | 1.0.0 |
| `chatgpt-desktop` | ask chatgpt, query chatgpt, generate image via chatgpt | — | 1.0.0 |
| `browser-game-builder` | build/clone/finish a browser·HTML5·canvas game, RTS/tower-defense/top-down shooter, add units·sprites·factions·game sfx·balance, 8-dir sprite facing | — | 1.0.0 |
| `vintage-ad-generator` | create original vintage/period ad artwork, heritage/nostalgia tee, Local Lore town ad, "fake old newspaper ad", vintage art "looks too AI" | — | 1.0.0 |
| `workspace-audit` | run an audit, audit my workspace/setup, check for drift, Audit N, /workspace-audit | — | 1.0.0 |
| `financial-plan-architect` | financial plan, budget, net worth, retirement/savings/debt-payoff plan, financial health check, bank/brokerage exports analysis, refresh my plan | — | 1.0.0 |
| `text-adventure` | text adventure, interactive fiction, IF game, Zork/Zork-like, parser game, "make me a text game", room-and-inventory game, MUD-like single-player (NOT Twine hypertext) | — | 1.0.0 |
| `genealogy-research` | family tree, genealogy, ancestor, GEDCOM, parish register, land grant, Find A Grave/WikiTree audit, Culley/Gore/Edens/Conway/Maloney/Marks/Milligan/Tucker | supersedes stale `skill-genealogy-research-agent` catalog ref | 1.0.0 |
| `3d-ai-studio-api` | 3D AI Studio API, text-to-3D, image-to-3D via 3daistudio | — | 1.0.0 |
| `drawio-skill` | diagram, flowchart, architecture diagram, draw.io/diagrams.net, .drawio export | — | 1.14.0 |
| `meshy-3d-generation` | Meshy API, text/image to 3D, texture a model, rig or animate a character | — | 1.0.0 |
| `meshy-3d-printing` | 3D print a generated model, slicer detection (Bambu/Orca/Prusa/Cura), print-prep | — | 1.0.0 |
| `research-access` | find academic papers, DOI lookup, open-access PDF, BibTeX export (research-access MCP) | — | 1.0.0 |
| `adhd-assistant` | ADHD-friendly task/life management, focus and reminder support | — | 1.0.0 |
| `agent-dashboard` | agent dashboard, monitor running agents | — | 1.0.0 |
| `bambu-print` | search Printables/MakerWorld, download a model, slice with BambuStudio CLI, send to Bambu printer | — | 1.0.0 |
| `find-skills` | discover and install agent skills, "what skills exist for X" | — | 1.0.0 |
| `general-writing` | write an article/essay/post/copy, general-purpose writing help | — | 1.0.0 |
| `goodreads` | Goodreads books, reading list, book ratings and reviews | — | 1.0.0 |
| `google-web-search` | grounded web search via the Gemini Google Search tool | — | 1.0.0 |
| `home-assistant-agent-secure` | control Home Assistant devices via the Assist/Conversation API | — | 1.0.0 |
| `local-places` | nearby places, restaurants/business lookup via Google Places | — | 1.0.0 |
| `mcp-workflow` | MCP workflow automation patterns, chain MCP tools | — | 1.0.0 |
| `office365-connector` | Microsoft Graph, Outlook/OneDrive/Teams, device-code OAuth, multi-account | — | 1.0.0 |
| `ollama-local` | run/manage local Ollama models, local LLM inference | — | 1.0.0 |
| `ralph` | write a PRD, RALPH BUILD LOOP automation with Claude Code | — | 1.0.0 |
| `stock-analysis` | analyze a stock or crypto, portfolio, watchlist, Yahoo Finance data | — | 6.2.0 |
| `voice-email` | send email by natural voice command, accessibility-oriented mail | — | 1.0.0 |
| `web-mcp` | WebMCP, expose a web app's actions as agent tools | — | 1.0.0 |
| `windows-control` | Windows GUI automation, click/type/dialog handling via pyautogui + UI Automation | — | 1.0.0 |
| `youtube-api` | YouTube API access without official-API quota | — | 1.0.0 |
| `youtube-data` | YouTube transcripts, metadata, channel info, search, playlists | — | 1.0.0 |
| `youtube-full` | full YouTube toolkit — search then transcript, channels, playlists, metadata | — | 1.0.0 |
| `youtube-playlist` | browse a YouTube playlist, fetch its videos' transcripts | — | 1.0.0 |
| `youtube-summary` | summarize a YouTube video into structured Markdown | — | 1.0.0 |

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
| `game-asset-pipeline` | slice/pack sprite sheet, get sprites into my game, sprite atlas, white halo on sprites, walk cycle jitters, character faces wrong way, render GLB/Meshy model to sprite, asset ingestion/packing | — | 1.0.0 |

## Installed standalone skills (~/.claude/skills)

All sarges-skills entries above are junctions into this repo (anti-sycophancy + chatgpt-desktop re-junctioned 2026-07-03, Audit 8 fix). Remaining third-party installs — marketplace junctions to `~\.agents\skills\`, plus a few loose dirs (drawio-skill, 3d-ai-studio-api, meshy-*): adhd-assistant, ollama-local, bambu-print, drawio-skill, stock-analysis, office365-connector, home-assistant-agent-secure, web-mcp, mcp-workflow, ralph, goodreads, local-places, google-web-search, windows-control, 3d-ai-studio-api, meshy-3d-generation, meshy-3d-printing, youtube-* (consolidation pending), voice-email (stub — delete), general-writing (broken — fix/delete).

## NOT skills (correct home is elsewhere)

| Old protocol | Home |
|---|---|
| Relay check (APP-LL-015) | SessionStart hook |
| File-org audit trail (APP-LL-019) | PreToolUse hook |
| Index Maintenance | Weekly scheduled task + monthly consolidate-memory |
| Anti-sycophancy defaults + footer, Versioning, Chunking, cloudId | CLAUDE.md |
| Tool Search, Context Limit, Atlassian session-start | Native — deleted |

See `Workspace Optimization\PROMPT_TREE_AUDIT.md` (Confluence 69926919) for the full mapping rationale.
