# rootnode-skills — vendored provenance

- **Upstream:** https://github.com/drayline/rootnode-skills
- **Author:** root.node / drayline (Aaron)
- **Commit SHA:** `6350e2b6869f41489f6bb810fbba1e05135b07e9` (branch `main`, committed 2026-07-28)
- **Latest upstream release at vendor time:** `catalog-v4.0` (published 2026-07-25), asset `rootnode-catalog-v4.0.zip`
- **License:** Apache-2.0 (`LICENSE`, Copyright 2025 root.node). No `NOTICE` file ships upstream — none fabricated here.
- **Vendored:** 2026-08-15 by Claude Code (Opus 5) via Desktop Commander.
- **Method:** clone to `C:\Claude\temp\ttl-rootnode`, robocopy `/E /XD .git` to this folder, temp deleted.

## Surface map (authoritative — from upstream `CLAUDE.md` + `build_release_artifacts.py`)

27 source folders, 29 release artifacts. Not every folder is a Claude Code skill.

- **Claude Code only (3):** `rootnode-critic-gate`, `rootnode-mode-router`, `rootnode-repo-hygiene`
- **Dual surface (2):** `rootnode-skill-builder`, `rootnode-cc-design`
- **chat-Project only (22):** every other `rootnode-*` folder

## Live install (Claude Code)

Directory junctions at `C:\Users\blain\.claude\skills\<name>` -> this folder's `<name>`:

- `rootnode-critic-gate`
- `rootnode-mode-router`
- `rootnode-repo-hygiene`
- `rootnode-skill-builder`
- `rootnode-cc-design`

The other 22 folders are deliberately NOT junctioned — they are chat-Project skills and do nothing useful in Claude Code.

## chat-Project bundles

`_chat-project-bundles\` holds the 24 `-cp.zip` release artifacts pulled from the
`catalog-v4.0` release bundle. These must be uploaded MANUALLY at
claude.ai -> Settings -> Capabilities -> Skills. Do not unzip them; do not junction them.

## Update procedure

Re-clone upstream, diff, re-robocopy over this folder, update the SHA above.
Junctions need no changes unless the surface map changes. Re-pull `-cp.zip`
artifacts from the new catalog release.
