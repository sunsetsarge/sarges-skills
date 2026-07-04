---
name: skill-home-assistant
description: >-
  Set up, optimize, and run a Home Assistant instance end-to-end — especially a
  Home Assistant Green running HAOS: connect to the live instance (official MCP
  Server integration, REST + WebSocket API, or the community ha-mcp server),
  inventory every entity / device / area / integration / add-on, build an
  intuitive mobile-first Lovelace dashboard (Sections views, tile cards, HACS
  cards like Mushroom), and propose + implement automations ranked by value ÷
  effort (motion lighting, presence, climate setback, leak/smoke alerts,
  actionable notifications) — with a backup-before-every-write safety model.
  USE THIS SKILL whenever the user mentions Home Assistant, HA, HAOS, Home
  Assistant Green, lovelace, dashboard, automation, blueprint, scene, script,
  zigbee, z-wave, thread, matter, ZHA, Zigbee2MQTT, HACS, smart home, entity,
  integration, ZBT-2, ZWA-2, Nabu Casa, Supervisor, or add-on — and whenever
  they ask to set up / tune / organize / add to / automate their smart home or
  smart devices, EVEN IF they never say "Home Assistant" ("build me a dashboard
  for my smart home", "what should I automate", "my motion lights are dumb",
  "help me set up my Green box"). Prefer this over improvising: HA ships
  monthly, syntax drifts, and the numbered rules here are the writes that have
  burned people before.
metadata:
  version: 1.0.0
---

# Home Assistant Green — Setup, Dashboard & Automation Operator

**Confluence sources for auto-sync:**

| Source Page | Page ID | Content |
|-------------|---------|---------|
| Home Assistant — Project Log | 80969753 | Session logs, instance-specific lessons |
| Project Logs hub | 98494 | Parent for HA project pages |

**Last synced:** 2026-07-04 | **Source version:** skill-home-assistant v1.0

Operate a live Home Assistant instance the way a careful integrator would:
**discover first, back up before every write, add — never clobber, and ship the
minimum useful thing before proposing more.** Built for the Home Assistant
Green (HAOS + Supervisor + add-ons + HACS all available) but degrades cleanly
to any HA install.

## The four pillars

1. **Setup & management** — connect, inventory everything, keep config healthy
   and backed up.
2. **Optimization** — missing integrations, messy registry, recorder bloat,
   backup gaps — surfaced as offers, never auto-applied.
3. **Dashboard** — one intuitive, mobile-first Sections dashboard tailored to
   the user's real rooms and devices.
4. **Automations** — a ranked shortlist that fits their actual daily life,
   implemented on approval with stable IDs and a documented undo.

## Reference files — read when needed

- [references/connect-and-discover.md](references/connect-and-discover.md) —
  read at Stage 1–2: the three control surfaces, detection procedure, token
  handling, full inventory recipe.
- [references/rest-websocket-api.md](references/rest-websocket-api.md) — read
  before any REST/WS call you haven't made this session: exact endpoints, WS
  command shapes, the Supervisor-via-WS gotcha, reload services.
- [references/dashboards.md](references/dashboards.md) — read at Stage 5:
  Sections view schema, card-per-domain map, HACS card catalog, merge-safe
  write procedure.
- [references/automations-cookbook.md](references/automations-cookbook.md) —
  read at Stage 6: modern (2024.10+) automation schema and the ranked pattern
  catalog with fit rationale + placeholders.
- [references/optimization.md](references/optimization.md) — read at Stage 7:
  the offer-only optimization checklist.
- [references/green-hardware.md](references/green-hardware.md) — read when
  hardware, radios (ZBT-2 / ZWA-2), add-ons, HACS install, or Nabu Casa come
  up.

Scripts (env `HA_URL` + `HA_TOKEN`, or `%USERPROFILE%\.ha-skill\secrets.json`):

- `scripts/discover.py` — full read-only inventory → JSON (`--out FILE`).
- `scripts/validate_yaml.py` — lint automation/dashboard YAML pre-apply
  (`--kind automation|dashboard`, `--live-check`).
- `scripts/backup.py` — trigger + confirm a Supervisor full backup.

Starter Lovelace fragments (merge, never replace):
`assets/dashboard-templates/overview.yaml`, `area-view.yaml`,
`function-views.yaml`.

## Picking the control surface (Stage 1 logic)

Detect what this session actually has — never assume:

1. **ha-mcp tools present** (community server, 80+ tools: config, automations,
   dashboards, registry, HACS)? → use it for everything; it wraps REST/WS.
2. **Official HA "MCP Server" integration tools present** (Assist-level)? →
   fine for *simple conversational control* of exposed entities only. It
   CANNOT edit config, automations, dashboards, or the registry.
3. **Neither, or structural work needed** → REST + WebSocket with a long-lived
   token (user profile → Security → long-lived access tokens). This is ground
   truth; the scripts use it.

**Rule of thumb: Assist-level MCP for simple control; REST/WS or ha-mcp for
anything STRUCTURAL (dashboards, automations, registry, HACS).** When both a
capable and a limited surface exist, take the capable one.

## Runtime workflow — stages in order

**Stage 1 — Connect & verify.** Detect surfaces (above), test the connection
(`GET /api/` or a trivial tool call), read HA version and
`installation_type` (Green = HA OS → Supervisor available). Failure here ends
the session with a clear fix (token, URL, VLAN/firewall).

**Stage 2 — Inventory (read-only, always safe).** Run `scripts/discover.py`
or the equivalent WS calls: entities grouped by domain AND by area, devices,
integrations, add-ons, HACS presence, dashboards, unavailable entities.
Summarize back in plain language ("3 areas, 14 lights, 6 motion sensors, no
media players configured…"). Everything downstream cites this inventory.

**Stage 3 — Assess needs.** Prefer to INFER priorities from the inventory
(cameras + door sensors → security; many lights + motion → ambiance/
convenience). Where you must ask, batch 2–4 short questions in ONE turn:
household routine, work-from-home, top priorities (convenience / security /
energy / ambiance), pain points. **Never block** — if unanswered, proceed with
sensible defaults and say which defaults you took.

**Stage 4 — Back up.** `scripts/backup.py` (WS `supervisor/api` →
`/backups/new/full`), confirm the slug exists. **No confirmed backup, no
write.** If Supervisor is absent, get the user to back up manually and confirm
before continuing.

**Stage 5 — Dashboard.** Propose a structure (views + what's on each) in
plain language, get confirmation, then implement per
[references/dashboards.md](references/dashboards.md): read current Lovelace
config, MERGE new views in, write via `lovelace/config/save`, re-read to
verify, show the result. Storage mode → stays UI-editable.

**Stage 6 — Automations.** Propose a ranked shortlist (value ÷ effort) from
the cookbook patterns that match the inventory — each with a one-line "fits
you because…". Get confirmation on which to build. Implement with stable
`id`/`unique_id`, validate (`scripts/validate_yaml.py`, then config check),
reload, and tell the user how to disable/undo each one.

**Stage 7 — Optimization.** Present the
[references/optimization.md](references/optimization.md) findings (missing
integrations, unassigned/messy entities, recorder tuning, backup schedule) as
an **offer with effort estimates — never auto-apply**.

**Stage 8 — Handoff.** Summary: what changed, where it lives (dashboard name,
automation aliases/IDs, backup slug), and exactly how to reverse each change.

## Hard-won rules

### Safety — writes

1. **Back up before every write.** Trigger a Supervisor full backup
   (`scripts/backup.py`; WS `{"type":"supervisor/api","endpoint":"/backups/new/full","method":"post"}`)
   and confirm the slug exists before editing any config, automation, or
   dashboard. No backup, no write.
2. **Never clobber.** ADD automations / dashboards / views: read current state
   first (`lovelace/config`, existing automation list) and merge — never
   overwrite or delete existing user config, even "obviously broken" bits.
3. **Validate before apply.** `scripts/validate_yaml.py`, then
   `POST /api/config/core/check_config`, before any reload or restart. Never
   restart HA blind.
4. **Confirm before write.** Present the concrete plan (what, where) and get
   explicit approval before applying. Reads are free; writes are gated.
5. **Prefer reload over restart.** `automation.reload`, `scene.reload`,
   targeted config reloads first; full restart only when required, with a
   warning about the ~1 min of downtime (automations dead, recordings gap).

### Identity & hygiene

6. **Unique IDs on everything you create.** Every automation/script/scene
   gets a stable `id` so it's UI-editable and re-saves update in place
   instead of duplicating. Preferred write path: ha-mcp's automation tools,
   or YAML + `automation.reload` (the frontend's
   `POST /api/config/automation/config/<id>` works but is undocumented and
   version-coupled — see the cookbook §2).
7. **Secret hygiene.** Never hardcode, echo, or log the long-lived token or
   any credential — scripts read `HA_URL`/`HA_TOKEN` from env or
   `%USERPROFILE%\.ha-skill\secrets.json`; mask tokens as `***` in all output
   and committed files.
8. **Discover before prescribe.** Never invent entities or areas — every
   card, trigger, and recommendation must cite a real `entity_id`/area from
   the Stage-2 inventory. Template placeholders (`PLACEHOLDER`, `# REPLACE:`)
   must never reach the live instance.
9. **Match the user's edit surface.** Ask once: UI-managed → keep everything
   storage-mode/UI-editable (the default); YAML-managed → respect their file
   layout and packages. Don't mix.
10. **Reversibility is part of done.** The Stage-8 handoff states, per change,
    how to undo it (toggle the automation off, remove the view, restore the
    named backup slug).

### API & platform gotchas

11. **Supervisor via WebSocket, not REST.** `/api/hassio/*` REST proxy 401s
    with core long-lived tokens; the reliable path is the WS command
    `{"type":"supervisor/api","endpoint":...,"method":...}`.
12. **Use the modern automation syntax.** Since 2024.10: plural `triggers:` /
    `conditions:` / `actions:`, `trigger:` (not `platform:`) inside trigger
    items, `action:` (not `service:`) in call steps. Legacy still parses —
    but write modern, per the cookbook.
13. **`POST /api/states/…` does NOT control devices.** It only overwrites the
    state object. To actually turn things on/off, call services:
    `POST /api/services/<domain>/<service>`.
14. **Sections views for anything new.** New dashboard views use
    `type: sections` (grid sections, heading cards, badges) — the modern,
    mobile-first, drag-editable layout. Don't emit legacy masonry views.
15. **HACS cards only after checking HACS.** Confirm HACS is installed (and
    which cards are) before proposing Mushroom / ApexCharts / etc. Built-in
    cards first; HACS is an upgrade offer.
16. **ZBT-2 is Zigbee OR Thread, never both** — one protocol per stick — and
    every radio stick goes on the **USB extension cable** away from USB-3
    ports (interference kills Zigbee/Z-Wave range).

### Scope discipline

17. **Ship the minimum useful thing first.** ONE working overview dashboard +
    3–5 highest-value automations, validated and live, BEFORE proposing more.
    No 12-view frameworks, no 30-automation batches. Rank by value ÷ effort
    and stop at "useful and used."
18. **Every proposal names its evidence.** One line per automation/card:
    "fits you because [inventory fact / stated priority]." If you can't write
    that line, cut the proposal.
19. **Optimization is an offer.** Registry renames, recorder excludes,
    integration adds — present with impact + effort, apply only what the user
    picks. Batch renames are previewed first (renaming `entity_id`s can break
    existing automations — check references before renaming).

## Personalization defaults

- Tailor to the actual inventory + stated priorities + areas. Map entity
  domains → applicable cards and automation patterns (tables in the dashboard
  and cookbook references).
- Batch questions (2–4 per turn, once per stage at most); never interrogate.
- For automation-first users: lead with toil-removal automations (presence,
  schedules, watchdog alerts) and single-action triggers over anything that
  needs daily manual input.
- HA ships monthly: when a schema detail matters and this skill's references
  might be stale, verify against home-assistant.io before writing to the live
  instance.
