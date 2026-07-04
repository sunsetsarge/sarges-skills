# Optimization Checklist — Offer, Never Auto-Apply

This is the skill's standing checklist for reviewing a Home Assistant instance (Green-focused, but
applies to any HA OS install). **The rule that governs every section below: surface findings as a
numbered list of proposed changes and wait for explicit approval before touching anything.** Never
silently rename entities, delete disabled entries, edit `configuration.yaml`, or fire WS calls that
mutate state without the user picking items off the list first. Read-only inspection is always fine
without asking.

Verified against home-assistant.io mid-2026 (HA ships monthly; re-check docs if this file is >6
months old). Confirmed 2026-07: Add-ons were renamed **Apps** in HA 2026.2 (Feb 2026) — expect both
terms in the wild for a while; this doc uses "Apps" going forward but calls out "add-on" where the
UI/API still literally says that (e.g. the `hassio` integration, `apps`/legacy `addons` REST paths).

## 1. Missing-integration discovery

Home Assistant surfaces devices it can see but hasn't been told to configure under **Settings →
Devices & Services → Discovered**. Walk this list first — it's free signal, zero risk to read.

- **Discovered-but-unconfigured integrations**: anything sitting in the discovery queue. Report each
  one with what it is and what adding it would unlock (e.g. "Sonos speaker found — adding gives you
  media_player + volume control + grouping"). Do not auto-confirm discovery cards.
- **Obvious gaps from the device inventory** — cross-reference what's physically in the house against
  what's configured:
  - Phones present (per the household/device list) but no `mobile_app` integration → no
    presence detection, no push notifications, no phone sensors (battery, location, activity).
  - Media players/TVs present but no Google Cast / DLNA / another cast integration configured →
    can't target them from `media_player.play_media` scripts or Assist.
  - Power-monitoring sensors (smart plugs, energy monitors) present with no **Utility Meter**
    helper wrapping them → no daily/monthly reset tracking, no cost sensor, Energy dashboard
    under-populated.
  - Thermostats/climate entities with no matching `climate` automation coverage.
- **Companion-app must-haves** — if the HA mobile app is installed on a phone but only partially
  set up, check for:
  - `device_tracker.<phone>` present and updating (not `unavailable`/stale) — this is presence
    detection, the backbone of most "someone came home" automations.
  - `notify.mobile_app_<phone>` reachable — test with a harmless notify call before assuming it
    works; a stale OAuth token or revoked notification permission fails silently.
  - Sensors the companion app can expose (battery %, screen state, activity, connectivity) —
    often present but disabled by default in the app's own sensor settings, not HA's.

Report format: **Integration/entity → what's missing → what it would unlock → risk of adding
(usually none, since integrations are additive)**. Let the user pick which to set up; some
(companion app notify, cast) need in-app taps you can't do for them.

## 2. Registry hygiene

Everything here is a **propose-then-apply** operation via the entity/device registry, most often
`config/entity_registry/update` over the WebSocket API (or the UI equivalent, Settings → Devices &
Services → Entities → pick entity → Settings tab).

- **Entities with no area assigned**: dashboards, the Areas view, and voice ("turn off the kitchen
  lights") all key off area assignment. List every entity with `area_id: null` whose device also
  lacks an area, grouped by integration, and propose an area for each — but the user confirms the
  actual room.
- **Cryptic default entity_ids / friendly names**: integrations that don't let you name the device
  during setup dump things like `switch.0x00124b0022334455`, `sensor.shellyplus1pm_a4cf12_switch_0`,
  or `binary_sensor.aqara_contact_2`. Flag these with a suggested human name, but see the RULE below
  before touching entity_ids specifically.
- **Disabled/unavailable entities** — these are not the same problem and need separate triage:
  - **Disabled by integration/user** (`disabled_by` set) — often intentional (someone disabled a
    noisy diagnostic sensor). List them, don't re-enable without asking.
  - **Unavailable, was previously available** — walk the entity's history/logbook. Categorize each
    as one of:
    - *Renamed/replaced* — a new entity_id appeared around the same time doing the same job
      (common after a device re-pair or integration migration). Propose retiring the old one.
    - *Battery dead* — check `sensor.<device>_battery` on the same device; if it's at 0% or has
      stopped reporting entirely, this is almost always the cause for battery-powered Zigbee/
      Z-Wave sensors going unavailable.
    - *Integration/hub broken* — the whole integration shows an error/reload-needed banner, or
      every entity under one hub (e.g. one Zigbee coordinator) went unavailable at once — points to
      the coordinator/USB stick, not the individual device. See the diagnostics section.
    - *Genuinely dead device* — battery is fine, no re-pair, integration healthy, still unavailable
      — flag for physical inspection/replacement.
- **Orphaned devices**: a device entry with zero entities left under it (all deleted or the
  integration removed) clutters Devices & Services with a dead card. Safe to propose removal once
  confirmed zero entities and zero automation/scene references.
- **Duplicate integrations**: the same physical hub/bridge configured twice (common after a
  Zigbee2MQTT → ZHA migration attempt, or re-adding a Hue bridge instead of reconfiguring it) —
  produces two full sets of entities for the same devices. Cross-check MAC/serial or entity count
  before flagging as a true duplicate.

**RULE — entity_id renames are batched, previewed, and approved, never done blind.** An entity_id is
load-bearing: automations, scripts, scenes, dashboards, and templates reference the literal string
(`sensor.shellyplus1pm_a4cf12_switch_0`), not the friendly name. Renaming the *friendly name* is
low-risk and can be proposed more freely. Renaming the *entity_id* itself:
1. Grep the config (automations.yaml, scripts.yaml, scenes.yaml, any Lovelace YAML, templates) for
   every reference to the old entity_id first.
2. Present the full rename batch as a table: old entity_id → new entity_id → files/references found.
3. Only rename after explicit approval, and note that HA does NOT auto-fix references inside YAML
   automations (it does fix its own internal registry links and Lovelace-UI-mode dashboards, but not
   hand-edited YAML or Jinja templates that string-match the id).
4. Never mass-rename an entire integration's entities in one blind pass — do it in reviewable
   batches per device/room.

## 3. Recorder / performance

- **Default `purge_keep_days` is 10 days.** Purge runs nightly at 04:12 local time by default;
  `recorder.purge` can be called manually. A **repack** runs automatically every second Sunday after
  purge to reclaim disk space — purging alone does not shrink the SQLite file, only repack does.
- **Exclude chatty entities** in `configuration.yaml` under `recorder:` — this is the single biggest
  lever on database size. Candidates to flag:
  - High-frequency numeric sensors with no long-term value (raw signal strength/RSSI, uptime
    counters, frequently-updating power/current sensors better served by long-term statistics than
    full history).
  - `automation`/`update`/`sun` domains if not needed in history.
  - Anything already covered by a **Utility Meter** or long-term statistics that doesn't need
    second-by-second detail retained.
  Use `exclude: domains:` / `entity_globs:` / `entities:`, or flip to an `include:`-only allowlist if
  the instance is small and the entity list is stable.
- **Green hardware limits make this matter more than on a NUC/Pi with an SSD**: Green ships with a
  **32 GB eMMC** flash drive (quad-core Cortex-A55, 4 GB RAM). eMMC has a finite write-endurance
  budget and no swap headroom to hide a bloated recorder DB — an unmanaged `home-assistant_v2.db`
  growing into the multi-GB range on 32 GB total storage is a real risk of filling the disk, not
  just a performance nit. Symptoms of recorder bloat on Green: History/Logbook UI slowing down,
  the frontend feeling laggy generally, `du -sh` on the config's db file creeping past ~1-2 GB,
  or the nightly purge/repack window visibly stalling Core.
- Diagnose growth with the `recorder.purge` + `repack: true` service call, or just check file size
  under `/config/home-assistant_v2.db`. If using MariaDB/Postgres via an add-on instead of the
  default SQLite, growth shows up as add-on disk usage instead.

## 4. Backup schedule

- **Built-in automatic backups**: Settings → System → Backups → "Set up backups" (as of the
  2026.x UI). Configure daily / specific-days / custom-time schedule and a retention count (e.g.
  keep the last 7 — HA deletes anything older automatically once the count is exceeded).
- **Encrypted by default**, stored as a compressed `.tar` archive. The user must download and keep
  the **backup emergency kit** (the encryption key) somewhere outside HA itself — an encrypted
  backup with a lost key is unrecoverable.
- **RULE: an on-box backup is not a backup strategy.** A backup living on the same eMMC/SSD that
  just failed protects against nothing — config mistakes, bad updates, accidental deletes, yes;
  hardware failure, no. Always pair the on-box schedule with an off-box copy:
  - **Home Assistant Cloud (Nabu Casa)**: automatic off-box copy, capped at 5 GB, stores the single
    most recent backup, always encrypted. Simplest option if already subscribed for remote
    access/voice.
  - **Network storage**: NAS (Synology, etc.) or cloud-drive integrations (Google Drive, OneDrive)
    via the relevant backup-location integration — keeps multiple historical backups off-box, not
    capped at one like the Cloud option.
  - Recommend at minimum one off-box destination; recommend both (Cloud + NAS/drive) if the
    instance controls anything safety-relevant (locks, alarm, garage).
- Before any Core/OS update: confirm a fresh backup exists and is off-box-verified, not just
  scheduled — "scheduled" and "actually ran successfully last night" are different claims; check the
  Backups list for a recent green checkmark before proceeding.

## 5. Update hygiene

- **Core ships roughly monthly** (`2026.M.0`, with `.1`/`.2` point releases for regressions). OS and
  Supervisor update on their own, slower cadence.
- **Read the breaking-changes section of the release notes before updating Core**, not after — HA
  publishes this per-release on home-assistant.io/blog and it specifically calls out config changes,
  removed YAML keys, and integrations needing re-auth. This is where "the update broke my
  automations" complaints trace back to, almost always avoidably.
- **Apps (formerly add-ons) update independently** of Core — Z-Wave JS UI, Mosquitto, Matter Server,
  File editor, etc. each have their own changelog under their Apps page. Update one at a time, not
  in a batch-and-pray, if the instance runs anything safety-relevant.
- **When to update vs. defer**:
  - Update promptly for security-fix point releases and anything explicitly patching a CVE.
  - Defer a `.0` release a few days to a week if the household depends on stability (Blaine's
    pattern: don't be the first one to hit a regression) — check the community forum/GitHub issues
    for the fresh release before updating a system with kid-facing or security-facing automations.
  - Never update Core and multiple Apps in the same window right before being unavailable to fix
    problems (e.g. don't update right before leaving town).

## 6. Diagnostics quick kit

Fast triage sequence before deeper digging or before a restart:

1. **`/api/error_log`** (or Settings → System → Logs in UI) — read the tail first; most "why is X
   broken" questions are answered by a stack trace already sitting there. Filter for the integration
   domain in question.
2. **Unavailable-entity sweep** — Settings → Entities, filter by state `unavailable`/`unknown`,
   sorted by integration. A cluster under one integration/device = hub problem (see registry hygiene
   §2 categorization above); scattered singletons = individual device problems (batteries, range).
3. **Reload the integration before restarting Core.** Settings → Devices & Services → the
   integration's `⋮` menu → **Reload** re-runs setup without a full restart — fixes most transient
   auth-token/connection-drop issues in seconds versus a multi-minute Core restart. Only escalate to
   a full restart if reload doesn't clear the error, and only escalate to a full OS reboot if a
   restart doesn't clear it.
4. Cross-check the Apps (add-ons) log for the specific app if the failing integration depends on one
   (Z-Wave JS UI, Mosquitto, Matter Server) — the Core log will show a connection failure, but the
   *why* usually lives in the app's own log.
