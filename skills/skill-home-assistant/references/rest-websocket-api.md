# REST & WebSocket API Reference

Ground-truth API this skill's scripts call directly. Exact shapes, copy-paste
curl/JSON. See `connect-and-discover.md` for how to choose this surface vs.
the MCP integration vs. ha-mcp, and for where `$HA_URL`/`$HA_TOKEN` come from.

## Table of contents

- [Auth](#auth)
- [REST endpoints](#rest-endpoints)
  - [GET /api/](#get-api)
  - [GET /api/config](#get-apiconfig)
  - [GET /api/states](#get-apistates)
  - [GET /api/states/<entity_id>](#get-apistatesentity_id)
  - [POST /api/states/<entity_id> — state-only caveat](#post-apistatesentity_id--state-only-caveat)
  - [POST /api/services/<domain>/<service>](#post-apiservicesdomainservice)
  - [GET /api/history/period/<timestamp>](#get-apihistoryperiodtimestamp)
  - [GET /api/logbook](#get-apilogbook)
  - [GET /api/error_log](#get-apierror_log)
  - [POST /api/template](#post-apitemplate)
  - [POST /api/config/core/check_config](#post-apiconfigcorecheck_config)
- [WebSocket API](#websocket-api)
  - [Auth handshake](#auth-handshake)
  - [ID sequencing](#id-sequencing)
  - [get_states / get_config / call_service / subscribe_events](#get_states--get_config--call_service--subscribe_events)
  - [Registries: area / device / entity](#registries-area--device--entity)
  - [entity_registry/update (renames, area assignment)](#entity_registryupdate-renames-area-assignment)
  - [Lovelace (dashboards)](#lovelace-dashboards)
  - [config_entries/get (integrations)](#config_entriesget-integrations)
- [Supervisor access from Core (HA OS gotcha)](#supervisor-access-from-core-ha-os-gotcha)
- [Config reloads](#config-reloads)

---

## Auth

Every REST call: `Authorization: Bearer <token>` header. Every WS session:
handshake first (below), then every command carries a client-chosen `id`.

```bash
curl -s -H "Authorization: Bearer $HA_TOKEN" \
     -H "Content-Type: application/json" \
     "$HA_URL/api/..."
```

---

## REST endpoints

### GET /api/

Liveness check.

```bash
curl -s -H "Authorization: Bearer $HA_TOKEN" "$HA_URL/api/"
# {"message": "API running."}
```

### GET /api/config

```bash
curl -s -H "Authorization: Bearer $HA_TOKEN" "$HA_URL/api/config"
```
Returns `version`, `location_name`, `time_zone`, `unit_system`, `components`
(loaded component list), and **`installation_type`** — use this to detect
`Home Assistant OS` vs `Home Assistant Container`/`Home Assistant Core`
before attempting any Supervisor call (HA Green always reports
`Home Assistant OS`).

### GET /api/states

```bash
curl -s -H "Authorization: Bearer $HA_TOKEN" "$HA_URL/api/states"
```
Array of `{entity_id, state, attributes, last_changed, last_updated, context}`
for every entity. This is the full state snapshot — filter/group client-side.

### GET /api/states/<entity_id>

```bash
curl -s -H "Authorization: Bearer $HA_TOKEN" "$HA_URL/api/states/light.living_room"
```
404 if the entity doesn't exist.

### POST /api/states/<entity_id> — state-only caveat

```bash
curl -s -X POST -H "Authorization: Bearer $HA_TOKEN" -H "Content-Type: application/json" \
  -d '{"state": "on", "attributes": {"brightness": 200}}' \
  "$HA_URL/api/states/light.living_room"
```
**This sets HA's internal representation of the state. It does NOT call the
device or an integration.** The light won't actually turn on — HA will just
*believe* it's on until the next real update overwrites it. Use this only for
virtual/template entities you own, never to control a real device. To
actually control something, use `POST /api/services/...` below. Returns 200
if the entity existed, 201 if this created a new one.

### POST /api/services/<domain>/<service>

This is how you actually control devices.

```bash
curl -s -X POST -H "Authorization: Bearer $HA_TOKEN" -H "Content-Type: application/json" \
  -d '{"entity_id": "light.living_room", "brightness": 200}' \
  "$HA_URL/api/services/light/turn_on"
```
Returns the array of changed states. Append `?return_response` to the URL to
get a service's optional structured response back (some services, e.g.
`weather.get_forecasts`, only return data this way):
```bash
curl -s -X POST ... "$HA_URL/api/services/weather/get_forecasts?return_response" \
  -d '{"entity_id": "weather.home", "type": "daily"}'
```

### GET /api/history/period/<timestamp>

```bash
curl -s -H "Authorization: Bearer $HA_TOKEN" \
  "$HA_URL/api/history/period/2026-07-01T00:00:00+00:00?filter_entity_id=sensor.temp&minimal_response=true"
```
`<timestamp>` is the start time (ISO 8601); omit it for "last day." Useful
params: `filter_entity_id` (comma-separated), `end_time`,
`minimal_response`, `no_attributes`, `significant_changes_only`.

### GET /api/logbook

```bash
curl -s -H "Authorization: Bearer $HA_TOKEN" "$HA_URL/api/logbook/2026-07-01T00:00:00+00:00"
```
Human-readable event log entries (domain, entity_id, message, timestamp).

### GET /api/error_log

```bash
curl -s -H "Authorization: Bearer $HA_TOKEN" "$HA_URL/api/error_log"
```
Plaintext, most-recent Core log — use for quick "did that just break
something" checks.

### POST /api/template

```bash
curl -s -X POST -H "Authorization: Bearer $HA_TOKEN" -H "Content-Type: application/json" \
  -d '{"template": "{{ states(\"sensor.temp\") }}"}' \
  "$HA_URL/api/template"
```
Renders a Jinja template server-side, returns plaintext. Good for testing
template logic before putting it in an automation/sensor.

### POST /api/config/core/check_config

```bash
curl -s -X POST -H "Authorization: Bearer $HA_TOKEN" "$HA_URL/api/config/core/check_config"
# {"result": "valid", "errors": null}
```
Validates YAML config **without restarting**. Always run this after any file
edit that touches `configuration.yaml` or included YAML, before triggering a
reload/restart.

---

## WebSocket API

Endpoint: `$HA_URL` with `ws://`/`wss://` scheme + `/api/websocket`.

### Auth handshake

```json
// server -> client, immediately on connect
{"type": "auth_required", "ha_version": "2026.7.0"}
```
```json
// client -> server
{"type": "auth", "access_token": "<HA_TOKEN>"}
```
```json
// server -> client, success
{"type": "auth_ok", "ha_version": "2026.7.0"}
```
```json
// server -> client, failure — reconnect will not help, token is bad
{"type": "auth_invalid", "message": "Invalid access token or password"}
```
No commands may be sent before `auth_ok`.

### ID sequencing

Every client message after auth needs a unique, client-chosen integer `id`
(convention: start at 1, increment). The server echoes that `id` on every
response/event tied to it, so pick a monotonically increasing counter per
connection and never reuse an id within the same connection.

```json
{"id": 1, "type": "get_states"}
```
```json
{"id": 1, "type": "result", "success": true, "result": [ ... ]}
```

### get_states / get_config / call_service / subscribe_events

```json
{"id": 2, "type": "get_states"}
{"id": 3, "type": "get_config"}
{"id": 4, "type": "call_service", "domain": "light", "service": "turn_on",
 "target": {"entity_id": "light.living_room"},
 "service_data": {"brightness": 200}, "return_response": false}
{"id": 5, "type": "subscribe_events", "event_type": "state_changed"}
```
`subscribe_events` returns an immediate `result` ack, then pushes ongoing
`{"id": 5, "type": "event", "event": {...}}` messages until you disconnect or
send `unsubscribe_events`.

### Registries: area / device / entity

```json
{"id": 6, "type": "config/area_registry/list"}
{"id": 7, "type": "config/device_registry/list"}
{"id": 8, "type": "config/entity_registry/list"}
```
- `config/area_registry/list` -> array of `{area_id, name, floor_id, icon, ...}`.
- `config/device_registry/list` -> array of `{id, name, manufacturer, model, area_id, config_entries, ...}`.
- `config/entity_registry/list` -> array of `{entity_id, device_id, area_id, platform, disabled_by, ...}`. Note `area_id` here may be `null` if the entity inherits its area from its parent device — fall back to the device's `area_id` in that case.

There is also a lighter-weight `config/entity_registry/list_for_display`
that returns a more compact shape (fewer fields) — prefer the full
`list` command when you need `platform`/`disabled_by`, use `list_for_display`
only for a quick name/id/area pass over a huge entity count.

### entity_registry/update (renames, area assignment)

```json
{"id": 9, "type": "config/entity_registry/update",
 "entity_id": "light.old_name",
 "name": "Living Room Lamp",
 "area_id": "living_room"}
```
Result echoes the updated entry. Renaming here changes `entity_id`'s
*friendly name*/area, not the `entity_id` string itself — pass `new_entity_id`
in the same payload if you also need to change the id (this does trigger a
real entity-id migration, take a backup first).

### Lovelace (dashboards)

```json
{"id": 10, "type": "lovelace/dashboards/list"}
```
-> array of configured dashboards (`url_path`, `title`, `mode`: `storage` or
`yaml`).

```json
{"id": 11, "type": "lovelace/config", "url_path": null}
```
Reads the dashboard config. Omit `url_path` (or pass `null`) for the default
dashboard; pass a specific `url_path` for additional dashboards. **Only
works for `storage`-mode dashboards** — a `yaml`-mode dashboard's config
lives in a file on disk, not in the registry, and this call will error for it.

```json
{"id": 12, "type": "lovelace/config/save", "url_path": null,
 "config": { "title": "Home", "views": [ ... ] }}
```
Writes the full dashboard config back. **This is a full-document replace,
same gotcha as Confluence page updates** — read the current config first,
mutate it in memory, then save the whole thing back. There is no partial/
patch mode.

These three Lovelace commands are real and shipped, but sparsely documented
in the official WebSocket API docs — cross-check against the
`home-assistant/frontend` source (`src/data/lovelace/*`) if a payload shape
here stops matching a future HA version, and prefer ha-mcp's dashboard tools
when ha-mcp is connected (it wraps this correctly for you).

### config_entries/get (integrations)

```json
{"id": 13, "type": "config_entries/get"}
```
Returns every configured integration instance: `entry_id`, `domain`,
`title`, `state` (`loaded`, `setup_error`, `not_loaded`, ...), `source`,
`disabled_by`. **Verify the exact command name against the running
version** — this has been referred to inconsistently as
`config_entries/get` (current/most common) vs. an older `config_entries/list`
in some client libraries; if a call returns `unknown_command`, retry with
the other name. There is no dedicated REST equivalent — config entries are
WS/UI-only, unlike states/services.

---

## Supervisor access from Core (HA OS gotcha)

**HA Green runs Home Assistant OS, which has a Supervisor** managing add-ons,
backups, and the OS itself. Only attempt this section if
`/api/config` -> `installation_type` is `Home Assistant OS`.

**Hard-won gotcha: the REST proxy path `/api/hassio/...` frequently returns
401 even with a valid Core long-lived token.** The Core-issued token doesn't
always carry Supervisor-proxy auth the way you'd expect, and this bites
people constantly. **The reliable path is the WebSocket `supervisor/api`
command** — use it as primary, treat the REST hassio proxy as a fallback
you should expect to fail:

```json
{"id": 14, "type": "supervisor/api", "endpoint": "/backups", "method": "get"}
```
List backups.

```json
{"id": 15, "type": "supervisor/api", "endpoint": "/backups/new/full",
 "method": "post", "data": {"name": "pre-change-2026-07-04"}}
```
Create a full backup. **Always do this before any structural change**
(registry edits, add-on installs, config entry changes).

```json
{"id": 16, "type": "supervisor/api", "endpoint": "/addons", "method": "get"}
```
List installed add-ons (slug, name, version, state, update-available).

```json
{"id": 17, "type": "supervisor/api", "endpoint": "/supervisor/info", "method": "get"}
```
Supervisor version, channel, arch, whether a Supervisor update is pending.

If REST is the only surface available for some reason (e.g. no WS library
handy in a quick script) and you must try the proxy path:
```bash
curl -s -H "Authorization: Bearer $HA_TOKEN" "$HA_URL/api/hassio/backups"
```
— but budget time for this to 401 and fall back to the WS form above rather
than assuming the token is bad.

---

## Config reloads

Prefer a **targeted reload** over a full restart — it's faster and doesn't
drop the WebSocket/UI session:

| Domain | Service |
|---|---|
| Automations | `automation.reload` |
| Scenes | `scene.reload` |
| Scripts | `script.reload` |
| Templates | `template.reload` |
| Core config (`configuration.yaml` top-level, `homeassistant:` block) | `homeassistant.reload_core_config` |
| Input helpers (`input_boolean`, `input_number`, etc.) | `<domain>.reload`, e.g. `input_boolean.reload` |
| Groups | `group.reload` |

```bash
curl -s -X POST -H "Authorization: Bearer $HA_TOKEN" -H "Content-Type: application/json" \
  -d '{}' "$HA_URL/api/services/automation/reload"
```

**Always run `POST /api/config/core/check_config` first** if you touched raw
YAML — a reload of invalid YAML can leave that domain broken until fixed.

**Last resort: `homeassistant.restart`** — full Core restart, drops all
connections, takes 30-90s. Only use when a targeted reload doesn't cover the
change (e.g. a new integration's initial setup, a Python-level component
change, or when a targeted reload service doesn't exist for what changed).
Never restart to work around a check_config failure — fix the YAML first.
