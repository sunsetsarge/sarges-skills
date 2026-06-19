# cully-skills

Blaine's personal Claude Code skill library. Source of truth for operational skills migrated out of the retired Confluence **Master Prompt Hub** (see `Workspace Optimization\PROMPT_TREE_AUDIT.md` / Confluence 69926919).

## Architecture

| Layer | Where | Role |
|---|---|---|
| **Source of truth** | this git repo (`C:\Claude\cully-skills`) | Versioned, diffable, the canonical copy |
| **Live install** | `~/.claude/skills/<name>` | Copied (or symlinked) here so Claude Code loads them |
| **Catalog** | Confluence "Skills Catalog" page | Human-readable index — what each skill does, trigger, version, source path. NOT the binaries |
| **Distribution (optional)** | push this repo to GitHub, add as a marketplace in `settings.json` | `git pull` install across machines / sharing |

**Why git, not Confluence, holds the artifacts:** skills are folders of code. Git gives versioning, diffing, and `git pull` install; a wiki gives none of that and drifts. Confluence's job here is the human catalog, not the download store.

## Install a skill locally (works today)

```powershell
Copy-Item -Recurse -Force "C:\Claude\cully-skills\skills\digitalnc-harvest" "C:\Users\blain\.claude\skills\digitalnc-harvest"
```

Then it loads on next session and fires on its trigger keywords.

## Distribute via marketplace (optional, needs GitHub)

1. Push this repo to GitHub (e.g. `github.com/sunsetsarge/cully-skills`).
2. Validate `.claude-plugin/marketplace.json` against the current Claude Code plugin docs (schema evolves — confirm before relying on it).
3. Add to `~/.claude/settings.json` under `extraKnownMarketplaces`, like the 6 marketplaces already there.

## Skills in this repo

| Skill | Replaces (old Hub protocol) | Status |
|---|---|---|
| `digitalnc-harvest` | APP-LL-024 Newspaper Harvest | ✅ authored |
| `goal` (planned) | APP-LL-023 /goal | ⬜ next |

Most old Hub protocols did **not** become skills — they're already covered by the `anthropic-skills` plugin (3d-printing, comfyui, powershell, lego, project-session), or moved to hooks (relay check, file-org audit), scheduled tasks (index maintenance), or CLAUDE.md (anti-sycophancy defaults, versioning). See the Prompt-Tree Audit for the full mapping.

## Conventions

- One skill per folder under `skills/`. Edit in place under git; never suffix-version.
- `SKILL.md` frontmatter `description` must contain the trigger keywords (that's what activates it).
- Skills that wrap existing validated scripts **point to them, they don't copy them** — honor the DO-NOT-REBUILD mandate.
