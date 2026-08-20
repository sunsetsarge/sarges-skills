# Third-Party Skills — Credits & Sources

These skills are **installed on Blaine's machine but authored by others**. This file is a **cited inventory, not a redistribution** — the skill code is *not* copied into this repo. Install each from its own source; verify its license before reuse.

**Why referenced, not vendored:** none of these shipped a `LICENSE` file, so their terms are mostly unconfirmed. Listing names + upstream links infringes nothing; copying the code would. If you later confirm a permissive license for one, it can be vendored into a `third-party/<name>/` folder with its LICENSE preserved.

Provenance pool (the marketplaces configured in `~/.claude/settings.json`): `rodin3d-skills` (DeemosTech), `prompts.chat` (f/prompts.chat), `claude-code-plugins` (anthropics/claude-code), `everything-claude-code` (affaan-m), `mcp-use` (mcp-use), `firebase` (firebase/firebase-tools). Several skills below self-identify as **OpenClaw** skills in their own descriptions.

## Confirmed license + author

| Skill | Author / Homepage | License | Notes |
|---|---|---|---|
| `drawio-skill` | Agents365-ai — github.com/Agents365-ai/drawio-skill | **MIT** | Bundles lobe-icons (MIT) + jgraph/drawio-mcp (Apache-2.0); draw.io desktop by jgraph |
| `meshy-3d-generation` | meshy-dev — github.com/meshy-dev/meshy-3d-agent | **MIT** | Meshy AI API client |
| `meshy-3d-printing` | meshy-dev — github.com/meshy-dev/meshy-3d-agent | **MIT** | Meshy AI API + slicer integration |
| `rpgmaker-core`, `rpgmaker-dialog`, `rpgmaker-database`, `rpgmaker-events`, `rpgmaker-consistency` | nightquill — github.com/nightquill/rpgmaker-agent-skills | **MIT** | **Vendored** at `third-party/rpgmaker-agent-skills/` (LICENSE preserved) @ `4766c49`, installed 2026-08-08. Junctioned into `~/.claude/skills/`. Each `SKILL.md` carries an appended `## LOCAL INSTALL NOTE` block (pack root, `C:\AI-Shared\python.exe`, Stormlight default project, MCP-vs-skills division of labor) — strip or re-apply that block when updating from upstream. |

### Added 2026-08-15 — Reddit skills-thread audit intake

| Skill(s) | Author / Homepage | License | Notes |
|---|---|---|---|
| `task-observer` | Eoghan Henn / rebelytics — github.com/rebelytics/one-skill-to-rule-them-all | **CC BY 4.0** | **Vendored** at `third-party/one-skill-to-rule-them-all/` (LICENSE.txt preserved) @ `281f134`, installed 2026-08-15. Junctioned into `~/.claude/skills/task-observer`. SKILL.md sits at repo root — junction targets the pack root, no nested skill dir. Left byte-identical to upstream (no LOCAL INSTALL NOTE block) so it updates cleanly; provenance in `VENDORED.md`. **Needs a CLAUDE.md activation line** — description matching alone is not enforceable and it will nag once per session until added. Writes to `<workspace>/skill-observations/log.md`; pin a stable log path before real use. |
| `rootnode-critic-gate`, `rootnode-mode-router`, `rootnode-repo-hygiene`, `rootnode-skill-builder`, `rootnode-cc-design` | drayline — github.com/drayline/rootnode-skills | **Apache-2.0** | **Vendored** at `third-party/rootnode-skills/` (LICENSE preserved, no NOTICE upstream) @ `6350e2b`, release catalog-v4.0, installed 2026-08-15. **5 of 27 junctioned** — upstream's surface map marks the other 22 as chat-Project-only; junctioning all 27 would pollute Claude Code skill-selection. 24 `-cp.zip` chat bundles staged at `third-party/rootnode-skills/_chat-project-bundles/` for manual upload (release assets, not in the git tree). `critic-gate` + `mode-router` are inert until a profile from the chat-side `rootnode-profile-builder` exists. `cc-design` REMEDIATE consumes `HYGIENE_REPORT.md` from `repo-hygiene` — run hygiene first. |

## License unconfirmed (no LICENSE file shipped)

| Skill | Likely source / author | License | Notes |
|---|---|---|---|
| `3d-ai-studio-api` | 3D AI Studio (3daistudio.com) | unconfirmed | API client; needs `3D_AI_STUDIO_API_KEY` |
| `adhd-assistant` | OpenClaw skill collection (per description) | unconfirmed | ADHD life-management |
| `agent-dashboard` | OpenClaw skill collection (per description) | unconfirmed | Agent status dashboard |
| `office365-connector` | OpenClaw skill collection (per description) | unconfirmed | MS Graph email/calendar/contacts |
| `voice-email` | OpenClaw skill collection | unconfirmed | Stub — flagged for deletion |
| `home-assistant-agent-secure` | unconfirmed (ships README) | unconfirmed | HA Assist/Conversation API |
| `stock-analysis` | unconfirmed (ships README) | unconfirmed | Yahoo Finance analysis |
| `google-web-search` | unconfirmed (ships README) | unconfirmed | Gemini-grounded search |
| `web-mcp` | unconfirmed | unconfirmed | WebMCP standard for Next.js/React |
| `mcp-workflow` | unconfirmed (Jason Zhou-inspired, per description) | unconfirmed | MCP workflow patterns |
| `ralph` | unconfirmed | unconfirmed | RALPH build-loop / PRD workflow |
| `bambu-print` | unconfirmed | unconfirmed | BambuStudio CLI + model-repo search |
| `goodreads` | unconfirmed | unconfirmed | Goodreads via browser automation |
| `local-places` | unconfirmed | unconfirmed | Google Places proxy |
| `windows-control` | unconfirmed | unconfirmed | Windows desktop control |
| `ollama-local` | unconfirmed | unconfirmed | Local Ollama management |
| `find-skills` | unconfirmed (Anthropic/community) | unconfirmed | Skill discovery |
| `general-writing` | unconfirmed (Anthropic/community) | unconfirmed | Broken SKILL.md — flagged fix/delete |
| `youtube-api` | unconfirmed (TranscriptAPI.com-based) | unconfirmed | Redundant — see consolidation note |
| `youtube-data` | unconfirmed (TranscriptAPI.com-based) | unconfirmed | Redundant |
| `youtube-full` | unconfirmed (TranscriptAPI.com-based) | unconfirmed | Keep (rename `youtube`) |
| `youtube-playlist` | unconfirmed (TranscriptAPI.com-based) | unconfirmed | Redundant |
| `youtube-summary` | unconfirmed (youtube2md-based) | unconfirmed | Keep (unique: markdown summaries) |

## Anthropic first-party (via `anthropic-skills` plugin — not in `~/.claude/skills`)

Listed for completeness; these are Anthropic's and installed via the plugin marketplace, **not** redistributed here: `skill-3d-printing`, `skill-comfyui`, `skill-powershell`, `skill-lego`, `skill-project-session`, `skill-genealogy-research-agent`, `docx`, `pdf`, `pptx`, `xlsx`, `consolidate-memory`, `ingest-resource`, `improve-system`, `skill-creator`, `ask-the-board`, `internal-focus-group`, `web-scraping`.

---

*To regenerate this inventory, re-scan `~/.claude/skills` frontmatter for `license`/`author`/`homepage` and reconcile against the marketplace list above. Last compiled: 2026-06-12.*
