# Connect & Discover

How a Claude session figures out which control surface it has for a given
Home Assistant instance (typically HA Green, running Home Assistant OS), and
how to inventory the instance safely before doing anything else.

## The three control surfaces

### 1. Official "Model Context Protocol Server" integration (HA 2025.2+)

- Built into Home Assistant core as the `mcp_server` integration.
- Exposed at `/api/mcp`, speaks Streamable HTTP, requires a bearer token
  (supports OAuth via HA's own Authentication API too).
- Routes everything through the **Assist API** — the same conversation/intent
  layer used by voice assistants.
- **Sees and controls ONLY entities the user has explicitly exposed** to
  Assist (Settings -> Voice assistants -> Expose, or per-entity exposure
  toggle). Anything not exposed is invisible to this surface.
- Ships a `GetLiveContext` tool that returns a plain-text snapshot resource
  (`homeassistant://assist/context-snapshot`) of current exposed-entity state.
- **CANNOT**: edit automations, scripts, scenes, dashboards, the entity
  registry, areas/devices, integrations, or add-ons. It is read/act on
  exposed entities only — good for "turn off the lamp," useless for
  "add an automation."
- No sampling, no server-initiated notifications.
- Good fit: safe conversational control with a locked-down blast radius.

### 2. REST API + WebSocket API (ground truth)

- Native to Home Assistant Core itself (`/api/*` REST, `/api/websocket` WS).
- Requires a **long-lived access token** (see below) sent as
  `Authorization: Bearer <token>`.
- Everything else — the frontend, the official MCP integration, ha-mcp — is
  a wrapper over these two APIs. If you need to know what's *actually*
  possible, this is the source of truth. See `rest-websocket-api.md` in this
  same folder for exact request/response shapes.
- Full read AND full write: entity registry, device registry, area registry,
  config entries, dashboards (lovelace), automations-as-config, Supervisor
  (on HA OS), everything.
- No built-in exposure gate — a long-lived token has the same permissions as
  the user account it belongs to. Treat the token like a root credential.

### 3. ha-mcp — community MCP server

- Repo: `homeassistant-ai/ha-mcp` — "The Unofficial and Awesome Home
  Assistant MCP Server." <https://github.com/homeassistant-ai/ha-mcp>
- Wraps REST + WebSocket into **85+ MCP tools across ~28 categories**:
  Add-ons, Areas & Floors, Assist, Automations, Blueprints, Calendar, Camera,
  Dashboard(s), Device Registry, Energy, Entity Registry, Files, Groups,
  HACS, Helper Entities, History & Statistics, Integrations, Labels &
  Categories, Matter, Scenes, Scripts, Search & Discovery, Service & Device
  Control, System, Todo Lists, Utilities, Zones.
- Unlike the official integration, ha-mcp **can** edit automations, scripts,
  scenes, dashboards, entity-registry properties, helpers, areas, zones,
  groups, calendars, blueprints, and install/manage HACS.
- Two install paths:
  - **HA Add-on** (recommended) — runs inside Home Assistant via the add-on
    store; no token to manage, the add-on already has Supervisor access.
  - **Local/standalone** — runs on your machine (stdio, or via a setup
    wizard supporting 15+ AI clients including Claude Code/Desktop); needs
    `HOMEASSISTANT_URL` and `HOMEASSISTANT_TOKEN` env vars.
- **Verify current tool count/category names against the live GitHub README**
  before relying on an exact number in user-facing text — this project moves
  fast and the count in this doc may already be stale.

## Detection procedure

Run this at the start of any HA task, in order, stop at the first hit:

1. **Check the current MCP session for ha-mcp tools.** If tool names
   matching `mcp__ha-mcp__*` (or similarly namespaced) are already loaded or
   discoverable via `ToolSearch`, ha-mcp is connected — use it for anything
   structural.
2. **Check for the official MCP Server integration.** If a generic
   Assist-style tool set is present (e.g. a single `HassTurnOn`/`HassTurnOff`/
   `GetLiveContext`-style toolset scoped to exposed entities, no
   registry/dashboard tools), you have the official integration only —
   assume it CANNOT do structural edits, don't attempt them through it.
3. **Fall back to REST.** Test with:
   ```bash
   curl -s -H "Authorization: Bearer $HA_TOKEN" "$HA_URL/api/"
   # expect: {"message": "API running."}
   ```
   If that succeeds, you have ground-truth REST/WS access regardless of what
   MCP tooling exists. Use `rest-websocket-api.md` for exact calls.
4. If none of the above respond, stop and tell the user connectivity is
   broken before attempting anything else (don't guess at a fourth surface).

## Selection rule

- **Simple, safe conversational control of exposed entities** ("turn off the
  living room lamp," "what's the thermostat set to") -> prefer the
  Assist-level MCP integration if present. Smaller blast radius, no
  registry/config access even if something goes wrong.
- **Anything STRUCTURAL** — creating/editing automations, dashboards,
  entity registry changes (renames, area assignment), area/device
  management, HACS, add-ons, backups, Supervisor operations, bulk
  discovery/inventory — **use REST/WS directly, or ha-mcp if it's already
  connected.** The official integration cannot do any of this; don't try.
- When both ha-mcp and raw REST/WS are available, prefer ha-mcp for anything
  it has a dedicated tool for (fewer chances to get a payload shape wrong);
  drop to raw REST/WS for anything ha-mcp doesn't cover, using
  `rest-websocket-api.md`.

## Obtaining a long-lived access token

1. Log into the Home Assistant frontend as the user whose permissions you
   want the token to carry.
2. Click the user's profile (bottom-left avatar / name).
3. Scroll to **Security** tab -> **Long-lived access tokens** -> **Create
   Token**.
4. Name it descriptively (e.g. `claude-skill-2026-07`) and copy the token
   immediately — HA shows it exactly once.
5. Store it as described below. Revoke and reissue if it's ever pasted into
   a chat log, screenshot, or committed to a repo.

## Where the skill reads connection details

- **Environment variables `HA_URL` and `HA_TOKEN`** (or `HOMEASSISTANT_URL`
  / `HOMEASSISTANT_TOKEN` if a script is specifically talking to ha-mcp's
  standalone mode — check which convention the script you're running
  expects).
- Alternatively, a local secrets file outside any git repo or synced cloud
  folder (e.g. `C:\Claude\.credentials\ha_token.txt`), loaded at runtime.
- **NEVER**: hardcode the token in a script, print it to stdout/logs, commit
  it, or paste it into a chat transcript. Treat exactly like the Printify/
  Printful/other API-key handling pattern already used across
  `C:\Claude\Scripts`.
- If a script needs the token and neither the env var nor the secrets file
  is present, fail loudly and tell the user how to set one — don't prompt
  for it inline and don't fall back to an empty/default token.

## Full inventory procedure (read-only, always safe)

Run this whenever the user asks "what do I have" / before planning any
change, so recommendations are grounded in the real instance, not assumed
defaults.

1. **HA version + installation type**
   ```bash
   curl -s -H "Authorization: Bearer $HA_TOKEN" "$HA_URL/api/config" | jq '.version, .installation_type'
   ```
   `installation_type` distinguishes `Home Assistant OS` (HA Green — has a
   Supervisor, add-ons, backups) from `Home Assistant Container`/`Home
   Assistant Core` (no Supervisor — skip all `supervisor/api` calls; note
   Core/Supervised installs are deprecated/sunset as of late 2025, so an
   HA Green box should always report `Home Assistant OS`).

2. **Entities — grouped two ways**
   ```bash
   curl -s -H "Authorization: Bearer $HA_TOKEN" "$HA_URL/api/states"
   ```
   Group client-side:
   - **By domain**: split each `entity_id` on `.` and bucket by the prefix
     (`light`, `switch`, `sensor`, `climate`, ...).
   - **By area**: entity->area is NOT in `/api/states`. Cross-reference with
     the WS `config/entity_registry/list` (entity -> `area_id`, falling back
     to the parent device's area) and `config/area_registry/list` (area_id
     -> friendly name). See `rest-websocket-api.md` for exact WS payloads.

3. **Devices**: WS `config/device_registry/list` — device name, manufacturer,
   model, area, and which config entry (integration instance) owns it.

4. **Integrations (config entries)**: WS `config_entries/get` (see
   `rest-websocket-api.md` for the verified command name and caveats around
   `config_entries/list` naming drift across HA versions) — returns every
   configured integration instance, its domain, title, and state
   (`loaded`/`setup_error`/etc).

5. **Add-ons** (HA OS only): WS
   `{"type": "supervisor/api", "endpoint": "/addons", "method": "get"}` —
   list installed add-ons, versions, running state. Do not attempt this on
   Container/Core installs.

6. **HACS presence**: check for a `hacs` domain entry in the config-entries
   list from step 4, or look for `sensor.hacs` / the HACS integration
   showing up in `/api/config` components. Absence just means HACS isn't
   installed — not an error.

7. **Supervisor info** (HA OS only): WS
   `{"type": "supervisor/api", "endpoint": "/supervisor/info", "method": "get"}`
   — Supervisor version, arch, channel (stable/beta), whether an update is
   pending.

All seven steps are pure reads. Run the full set before proposing any
structural change so the plan is based on the actual instance, not a
guessed-at default HA install.
