# Vendoring record — one-skill-to-rule-them-all

- **Upstream:** https://github.com/rebelytics/one-skill-to-rule-them-all
- **Commit pinned:** `281f13466cd3a73e9ebc9d210907748e1941a3dd` ("Update plugin version to 2.0.0", 2026-07-17)
- **Plugin version:** 2.0.0
- **Author:** Eoghan Henn / rebelytics.com
- **License:** CC BY 4.0 (`LICENSE.txt` preserved verbatim from upstream)
- **Skill name (SKILL.md frontmatter):** `task-observer`
- **Vendored:** 2026-08-15
- **Layout note:** upstream ships `SKILL.md` at the REPO ROOT (no `skills/` subfolder),
  so the junction target is this folder itself.
- **Junction:** `C:\Users\blain\.claude\skills\task-observer` -> this folder
- **Local modifications:** NONE. Files copied verbatim from the pinned commit
  (`.git/` excluded). No `## LOCAL INSTALL NOTE` block appended, unlike
  `third-party/rpgmaker-agent-skills/`.

## TODO for Blaine

Add a row to `third-party/CREDITS.md` under "Confirmed license + author"
(left untouched here because it is a tracked file with work in progress):

| `task-observer` | Eoghan Henn / rebelytics — github.com/rebelytics/one-skill-to-rule-them-all | **CC BY 4.0** | **Vendored** at `third-party/one-skill-to-rule-them-all/` (LICENSE.txt preserved) @ `281f134`, installed 2026-08-15. SKILL.md is at the repo root, so the junction targets the pack root. Unmodified from upstream. |
