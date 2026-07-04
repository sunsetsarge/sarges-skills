# Home Assistant Automations Cookbook

Verified against home-assistant.io docs (automation basics/trigger/condition/action/yaml, scripts, troubleshooting) as of 2026-07. All YAML here uses the **modern schema**: plural `triggers:`/`conditions:`/`actions:` at the top level, singular `trigger:`/`condition:` keys inside each list item, and `action:` (not `service:`) for service-call steps. Legacy singular top-level keys and the old `platform:`/`service:` item keys still parse and run — HA hasn't removed them — but automations authored by this skill always use modern syntax.

## Table of Contents

1. [Schema Quick Reference](#1-schema-quick-reference)
2. [Non-Negotiables](#2-non-negotiables)
3. [Ranked Pattern Catalog](#3-ranked-pattern-catalog)
   - [3a. Motion/Occupancy Lighting](#3a-motionoccupancy-lighting-with-lux-gate--timeout)
   - [3b. Nobody-Home / Arrive / Leave](#3b-nobody-home--arrive--leave)
   - [3c. Sun-Based Lighting](#3c-sun-based-lighting)
   - [3d. Climate Setback](#3d-climate-setback)
   - [3e. Good-Night / Good-Morning Scenes](#3e-good-night--good-morning-scene-routines)
   - [3f. Door/Window Left Open](#3f-doorwindow-left-open--notify)
   - [3g. Motion-While-Away Security](#3g-motion-while-away--notify--camera-snapshot)
   - [3h. Leak/Smoke/CO Critical Alerts](#3h-leaksmokeco--critical-notification)
   - [3i. Low-Battery Sweep](#3i-low-battery-sweep)
   - [3j. Phantom-Load Watchdog](#3j-phantom-load--left-on-watchdog)
   - [3k. Actionable Mobile Notifications](#3k-actionable-mobile-notifications)
4. [Blueprints](#4-blueprints)
5. [Testing & Rollback](#5-testing--rollback)

---

## 1. Schema Quick Reference

### 1.1 Modern automation shape

```yaml
- id: "1751600000000"          # stable numeric string, UI-generated — see §2
  alias: "Kitchen motion light"
  description: >-
    Turns on the kitchen light when motion is detected and it's dark enough.
    Turns off 5 min after motion clears.
  mode: restart                 # single | restart | queued | parallel — see 1.4
  triggers:
    - trigger: state
      entity_id: binary_sensor.kitchen_motion
      to: "on"
  conditions:
    - condition: numeric_state
      entity_id: sensor.kitchen_illuminance
      below: 20
  actions:
    - action: light.turn_on
      target:
        entity_id: light.kitchen
```

**Note:** legacy files using singular top-level `trigger:`/`condition:`/`action:`, `platform:` inside a trigger, or `service:` inside an action step remain valid — but this skill always emits/edits into the modern form above.

### 1.2 Trigger types

| Type | Key fields | Example |
|---|---|---|
| **state** | `entity_id`, `to`, `from`, `for` | `{trigger: state, entity_id: binary_sensor.door, to: "on", for: "00:02:00"}` |
| **numeric_state** | `entity_id`, `above`/`below`, `for` | `{trigger: numeric_state, entity_id: sensor.temp, above: 26, for: "00:10:00"}` |
| **time** | `at` | `{trigger: time, at: "22:30:00"}` |
| **time_pattern** | `hours`/`minutes`/`seconds` | `{trigger: time_pattern, minutes: "/15"}` |
| **sun** | `event: sunset/sunrise`, `offset` | `{trigger: sun, event: sunset, offset: "-00:30:00"}` |
| **sun (elevation)** | use `numeric_state` on `sun.sun` `sun_elevation` attribute — sun trigger itself has no elevation param; template trigger is the common alternative | see §3c |
| **zone** | `entity_id`, `zone`, `event: enter/leave` | `{trigger: zone, entity_id: person.blaine, zone: zone.home, event: enter}` |
| **device** | integration-defined, authored via UI picker; YAML varies | not hand-authored — pull from UI export |
| **template** | `value_template`, `for` | `{trigger: template, value_template: "{{ is_state('device_tracker.phone','home') }}"}` |
| **mqtt** | `topic`, `payload` | `{trigger: mqtt, topic: "shellies/kitchen/relay/0", payload: "on"}` |

`for:` on **state**/**numeric_state**/**template** triggers means "must hold continuously this long before firing" — the standard way to build timeout/debounce without a separate `delay`.

### 1.3 Condition types

```yaml
conditions:
  - condition: state
    entity_id: alarm_control_panel.home
    state: "armed_away"
  - condition: numeric_state
    entity_id: sensor.outdoor_temp
    below: 5
  - condition: time
    after: "07:00:00"
    before: "22:00:00"
  - condition: zone
    entity_id: person.blaine
    zone: zone.home
  - condition: template
    value_template: "{{ states('sensor.washer_power') | float > 5 }}"
  - condition: or
    conditions:
      - condition: state
        entity_id: input_boolean.guest_mode
        state: "on"
      - condition: state
        entity_id: input_boolean.party_mode
        state: "on"
  - condition: and
    conditions: [ ... ]
  - condition: not
    conditions: [ ... ]
```

Conditions at the top level gate the **whole automation**. The same condition objects can be nested inside `choose:`/`if:` blocks in the actions to branch logic mid-sequence (see 1.4 continued below).

### 1.4 Key actions

```yaml
actions:
  # plain service/action call
  - action: light.turn_on
    target:
      entity_id: light.kitchen
    data:
      brightness_pct: 60

  # delay
  - delay: "00:05:00"

  # wait for something else to happen, with timeout
  - wait_for_trigger:
      - trigger: state
        entity_id: binary_sensor.kitchen_motion
        to: "off"
    timeout: "00:10:00"
    continue_on_timeout: true

  # branch: first matching block runs, else `default`
  - choose:
      - conditions:
          - condition: state
            entity_id: sun.sun
            state: "below_horizon"
        sequence:
          - action: light.turn_on
            target: { entity_id: light.kitchen }
      - conditions:
          - condition: state
            entity_id: sun.sun
            state: "above_horizon"
        sequence:
          - action: light.turn_off
            target: { entity_id: light.kitchen }
    default:
      - action: notify.notify
        data: { message: "Sun state unknown" }

  # simple two-way branch
  - if:
      - condition: numeric_state
        entity_id: sensor.kitchen_illuminance
        below: 20
    then:
      - action: light.turn_on
        target: { entity_id: light.kitchen }
    else: []

  # loop
  - repeat:
      count: 3
      sequence:
        - action: light.toggle
          target: { entity_id: light.kitchen }
        - delay: "00:00:01"

  # run several action chains concurrently
  - parallel:
      - action: notify.mobile_app_blaines_phone
        data: { message: "Left home" }
      - action: climate.set_temperature
        target: { entity_id: climate.house }
        data: { temperature: 62 }
```

### 1.5 `mode:` semantics — pick deliberately

| Mode | What happens on re-trigger while running | Typical use |
|---|---|---|
| **single** (default) | New run refused, warning logged | Anything where overlap is nonsensical or dangerous (arm alarm, send single notification) |
| **restart** | Current run is cancelled, new run starts fresh | **Motion-timeout lighting** — new motion event must reset the "turn off after N minutes" clock, not queue behind the old one |
| **queued** | New run waits, executes after current finishes, order preserved | Sequential actions that must not interleave (e.g., a multi-step notification/escalation chain triggered rapidly) |
| **parallel** | New run executes immediately alongside existing run(s) | Independent per-entity automations using one automation with a template covering many entities, where each run is self-contained |

**Gotcha:** the single most common automation bug is using `mode: single` (the default!) on a motion-light-with-timeout automation. A second motion event mid-timeout gets refused, the timer never resets, and the light turns off while someone is still standing there. Always set `mode: restart` for that pattern (see 3a).

---

## 2. Non-Negotiables

Every automation this skill creates or edits must have:

1. **A stable `id:`.** This is what makes an automation **UI-editable and safely re-runnable without duplication**. Persistence and dedup on save go through `id:` — saving with an `id:` that already exists in `automations.yaml` **overwrites that entry in place**; omit or change the `id:` and you get a **new, duplicate automation** instead of an update. Use a stable string (UI generates a millisecond-epoch string like `"1751600000000"`; a slug like `"kitchen_motion_light"` also works and is more readable in diffs — pick one convention and keep it).
2. **`alias:`** — human-readable name, shown in the UI and traces/logs.
3. **`description:`** — one or two plain-language sentences stating *intent*, not mechanism ("Keeps the porch light off overnight to save power," not "Sets light.porch to off"). Lets a future edit know whether a change preserves the original goal.
4. **Explicit `mode:`** — never rely on the implicit `single` default; state the mode chosen and why (see 1.5).

### How the config is actually persisted

- **UI path (normal, safe):** Settings → Automations & Scenes → edit → Save. Writes through HA's internal config-storage flow, keyed by `id:`, into `automations.yaml` (or wherever `automation: !include automations.yaml` points).
- **REST/API path:** HA's frontend calls an internal endpoint shaped like `POST /api/config/automation/config/<id>` (with `GET`/`DELETE` variants) to read/write one automation by id. **This endpoint is real and is what the UI editor uses, but it is not part of the documented public REST API** (developers.home-assistant.io/docs/api/rest lists only `/api/states`, `/api/services/<domain>/<service>`, `/api/config/core/check_config`, etc.) — treat it as an internal, version-coupled detail, not a stable contract. **Prefer** editing YAML directly (or via the file-editor/Studio Code Server add-on) plus `automation.reload`, which is documented and stable. Only script against the config endpoint after confirming it against the running HA version.
- **YAML-file path (what this skill does):** edit `automations.yaml` directly, keeping the same `id:` for an existing automation, then call `automation.reload` (§5) — the officially supported non-UI path for anything scripted.

### Disable vs delete

- **Disable (preferred first step when troubleshooting):** `automation.turn_off` targeting the automation's entity_id, or the on/off toggle next to the automation in Settings → Automations & Scenes. The automation config stays intact; nothing is lost.
  ```yaml
  actions:
    - action: automation.turn_off
      target:
        entity_id: automation.kitchen_motion_light
  ```
- **Delete:** remove the block from `automations.yaml` and call `automation.reload`, or use the UI's delete button. Only delete once you're sure the automation should not exist at all — for anything experimental, disable first, confirm nothing depends on it, delete later.

---

## 3. Ranked Pattern Catalog

Ordered by typical value ÷ effort for a home-lab setup like Blaine's (UniFi + HA + mobile_app notify already in place).

### 3a. Motion/Occupancy Lighting with Lux Gate + Timeout

**Requires:** `binary_sensor` (motion/occupancy), `sensor` (illuminance — optional but recommended), `light` (or `switch`).
**Fit rationale template:** "Fits you because you have a motion sensor and a light in {room} and want it to turn on only when it's actually dark, then turn off automatically instead of nagging you to do it."

```yaml
- id: "kitchen_motion_light"
  alias: "Kitchen motion light (lux-gated)"
  description: >-
    Turns on the kitchen light on motion when it's dim enough to matter,
    and turns it off 5 minutes after motion clears.
  mode: restart   # REQUIRED for this pattern — see 1.5
  triggers:
    - trigger: state
      entity_id: binary_sensor.kitchen_motion   # REPLACE: your motion sensor
      to: "on"
      id: motion
    - trigger: state
      entity_id: binary_sensor.kitchen_motion   # REPLACE: same sensor
      to: "off"
      for: "00:05:00"                            # timeout knob
      id: clear
  conditions: []
  actions:
    - choose:
        - conditions:
            - condition: trigger
              id: motion
            - condition: numeric_state
              entity_id: sensor.kitchen_illuminance      # REPLACE: your lux sensor
              below: 20                                  # tuning knob: lux threshold
          sequence:
            - action: light.turn_on
              target: { entity_id: light.kitchen }   # REPLACE
      default:
        - action: light.turn_off
          target: { entity_id: light.kitchen }     # REPLACE
```

**Tuning knobs:** lux threshold (`below: 20`), off-timeout (`for: "00:05:00"` on the clear trigger), swap `light.turn_on` for a scene/brightness `data:` block for time-of-day dimming. **No illuminance sensor?** Drop the `numeric_state` condition and gate on a `sun.sun` state condition instead (`state: below_horizon`).

### 3b. Nobody-Home / Arrive / Leave

**Requires:** `person` or `device_tracker`, `zone`.
**Fit rationale:** "Fits you because you track phones/people and want the house to react automatically when everyone leaves or the first person gets home."

```yaml
- id: "everyone_leaves_house"
  alias: "Everyone left home"
  description: "Turns off lights, sets thermostat back, and reminds to arm the alarm when the last person leaves."
  mode: single
  triggers:
    - trigger: zone
      entity_id:
        - person.blaine       # REPLACE
        - person.spouse       # REPLACE
      zone: zone.home
      event: leave
  conditions:
    - condition: zone
      entity_id: person.blaine     # REPLACE
      zone: zone.home
      state: "not_home"            # confirms nobody is actually left — combine per-person as needed
  actions:
    - action: light.turn_off
      target: { entity_id: all }
    - action: climate.set_temperature
      target: { entity_id: climate.house }   # REPLACE
      data:
        temperature: 62                       # tuning knob: setback temp
    - action: notify.mobile_app_blaines_phone   # REPLACE
      data:
        message: "House is empty — alarm armed?"
```

For **arrive**, mirror with `event: enter` and a `condition: state` on `alarm_control_panel` to auto-disarm only if it was in `armed_home`.

### 3c. Sun-Based Lighting

**Requires:** `light`, built-in `sun.sun` entity (no config needed).
**Fit rationale:** "Fits you because you want porch/outdoor lights on a natural schedule instead of a fixed clock time."

```yaml
- id: "porch_lights_sunset"
  alias: "Porch lights on at sunset"
  description: "Turns on the porch light 30 minutes before sunset."
  mode: single
  triggers:
    - trigger: sun
      event: sunset
      offset: "-00:30:00"     # tuning knob: negative = before, positive = after
  conditions: []
  actions:
    - action: light.turn_on
      target: { entity_id: light.porch }    # REPLACE

- id: "outdoor_lights_off_morning"
  alias: "Outdoor lights off at sunrise"
  description: "Turns off outdoor lights once the sun is up."
  mode: single
  triggers:
    - trigger: sun
      event: sunrise
      offset: "00:15:00"
  actions:
    - action: light.turn_off
      target: { entity_id: light.porch }    # REPLACE
```

**Elevation variant** (e.g., "turn on when it's actually getting dark, civil twilight" rather than exact sunset): the `sun` trigger has no elevation parameter, so use a **numeric_state** trigger on the `sun.sun` entity's `elevation` attribute instead:

```yaml
  triggers:
    - trigger: numeric_state
      entity_id: sun.sun
      attribute: elevation
      below: 3          # tuning knob: degrees above horizon
```

### 3d. Climate Setback

**Requires:** `climate`, optionally `person`/`schedule` helper.
**Fit rationale:** "Fits you because you want heating/cooling to back off automatically on a schedule or when nobody's home, instead of manually adjusting the thermostat."

```yaml
- id: "climate_night_setback"
  alias: "Climate night setback"
  description: "Lowers the target temperature overnight and restores it in the morning."
  mode: single
  triggers:
    - trigger: time
      at: "22:00:00"
      id: night
    - trigger: time
      at: "06:30:00"
      id: morning
  conditions: []
  actions:
    - choose:
        - conditions:
            - condition: trigger
              id: night
          sequence:
            - action: climate.set_temperature
              target: { entity_id: climate.house }   # REPLACE
              data:
                temperature: 64                       # tuning knob: night setback temp
      default:
        - action: climate.set_temperature
          target: { entity_id: climate.house }       # REPLACE
          data:
            temperature: 70                           # tuning knob: day temp
```

Combine with `condition: zone` on a `person` entity to skip the morning restore if nobody's home yet.

### 3e. Good-Night / Good-Morning Scene Routines

**Requires:** `scene`, or a button/`input_button`/voice trigger.
**Fit rationale:** "Fits you because you already do the same sequence of actions (lock up, dim lights, set alarm) every night and want it as one press or one phrase."

```yaml
- id: "goodnight_routine"
  alias: "Good night routine"
  description: "Applies the goodnight scene, locks doors, and arms the alarm."
  mode: single
  triggers:
    - trigger: state
      entity_id: input_button.goodnight     # REPLACE: dashboard button, or swap for a time trigger
      to: "on"
  actions:
    - action: scene.turn_on
      target: { entity_id: scene.goodnight }         # REPLACE — pre-built via UI scene editor
    - action: lock.lock
      target: { entity_id: lock.front_door }          # REPLACE
    - action: alarm_control_panel.alarm_arm_night
      target: { entity_id: alarm_control_panel.home } # REPLACE
```

`scene.turn_on` applies a pre-authored `scene` entity (states baked in via the scene editor) — use this over hardcoding individual `light.turn_on` calls in the automation itself, so the scene stays editable in one place. Good-morning routine mirrors this with `scene.goodmorning` and `lock.unlock`/`alarm_control_panel.alarm_disarm` swapped in, typically on a `time` or `sun` trigger instead of a button.

### 3f. Door/Window Left Open → Notify

**Requires:** `binary_sensor` (door/window class), `notify`/`mobile_app`, optionally `climate`.
**Fit rationale:** "Fits you because a door left open for a few minutes usually means someone forgot, not that they want it open — worth a nudge."

```yaml
- id: "door_left_open_notify"
  alias: "Door left open notification"
  description: "Notifies if a door stays open more than 5 minutes."
  mode: single
  triggers:
    - trigger: state
      entity_id: binary_sensor.back_door       # REPLACE
      to: "on"
      for: "00:05:00"                           # tuning knob: how long is "left open"
  conditions: []
  actions:
    - action: notify.mobile_app_blaines_phone     # REPLACE
      data:
        message: "Back door has been open for 5 minutes."
```

**Climate-pause variant** — pause conditioning while a door is open (saves energy), resume on close:

```yaml
- id: "climate_pause_door_open"
  alias: "Pause climate while door open"
  description: "Turns off climate control while the back door is open; restores previous mode on close."
  mode: restart
  triggers:
    - trigger: state
      entity_id: binary_sensor.back_door    # REPLACE
      to: "on"
      for: "00:02:00"
    - trigger: state
      entity_id: binary_sensor.back_door    # REPLACE
      to: "off"
  actions:
    - choose:
        - conditions:
            - condition: state
              entity_id: binary_sensor.back_door   # REPLACE
              state: "on"
          sequence:
            - action: climate.turn_off
              target: { entity_id: climate.house }   # REPLACE
      default:
        - action: climate.turn_on
          target: { entity_id: climate.house }      # REPLACE
```

### 3g. Motion-While-Away → Notify + Camera Snapshot

**Requires:** `binary_sensor` (motion), `camera`, `alarm_control_panel` or `person`/`zone` for "away" state, `notify.mobile_app_*`.
**Fit rationale:** "Fits you because you've got Protect cameras already — pairing motion with a snapshot notification turns them into a real alert instead of just a recording you check later."

```yaml
- id: "motion_while_away_snapshot"
  alias: "Motion while away — snapshot and notify"
  description: "Takes a camera snapshot and sends a push notification with the image when motion is detected while nobody is home."
  mode: single
  triggers:
    - trigger: state
      entity_id: binary_sensor.driveway_motion   # REPLACE
      to: "on"
  conditions:
    - condition: state
      entity_id: person.blaine    # REPLACE — or use alarm_control_panel state "armed_away"
      state: "not_home"
  actions:
    - action: camera.snapshot
      target: { entity_id: camera.driveway }   # REPLACE
      data:
        filename: "/config/www/snapshots/driveway_latest.jpg"
    - action: notify.mobile_app_blaines_phone   # REPLACE
      data:
        message: "Motion detected at the driveway while away."
        data:
          image: "/local/snapshots/driveway_latest.jpg"
```

**Gotcha:** the snapshot `filename:` path must be under `/config/www/` for the `/local/` URL in the notify `image:` to resolve; mismatched paths silently show no image in the push notification (no error is raised).

### 3h. Leak/Smoke/CO → Critical Notification

**Requires:** `binary_sensor` (moisture/smoke/carbon_monoxide device class), `notify.mobile_app_*`.
**Fit rationale:** "Fits you because these sensors exist specifically for the one time you're not watching — the notification needs to break through Do Not Disturb, not just chime like everything else."

```yaml
- id: "water_leak_critical_alert"
  alias: "Water leak critical alert"
  description: "Sends a critical, high-priority push notification immediately on leak detection — bypasses phone silent/DND."
  mode: single
  triggers:
    - trigger: state
      entity_id: binary_sensor.utility_room_leak    # REPLACE
      to: "on"
  actions:
    - action: notify.mobile_app_blaines_phone         # REPLACE
      data:
        message: "Water leak detected in the utility room!"
        data:
          push: { sound: { name: "default", critical: 1, volume: 1.0 } }  # iOS: critical bypasses silent/DND
          ttl: 0
          priority: high            # Android: high-priority heads-up notification
```

Same shape for smoke (`binary_sensor` device_class `smoke`) and CO (`carbon_monoxide`) — duplicate the block per sensor, or use one automation with a list of `entity_id`s and put the alarm type in the message via a template (`{{ trigger.to_state.attributes.friendly_name }}`).

### 3i. Low-Battery Sweep

**Requires:** any `sensor` with device_class `battery` (multiple).
**Fit rationale:** "Fits you because a dying sensor battery fails silently — a scheduled digest catches it before the sensor itself goes stale/unavailable."

```yaml
- id: "low_battery_daily_digest"
  alias: "Low battery daily digest"
  description: "Once a day, lists all battery-powered devices below 20% in a single notification."
  mode: single
  triggers:
    - trigger: time
      at: "08:00:00"
  conditions:
    - condition: template
      value_template: >-
        {{ states.sensor
           | selectattr('attributes.device_class', 'defined')
           | selectattr('attributes.device_class', 'equalto', 'battery')
           | selectattr('state', 'is_number')
           | selectattr('state', 'lt', '20')
           | list | count > 0 }}
  actions:
    - action: notify.mobile_app_blaines_phone    # REPLACE
      data:
        title: "Low battery devices"
        message: >-
          {{ states.sensor | selectattr('attributes.device_class', 'defined')
             | selectattr('attributes.device_class', 'equalto', 'battery')
             | selectattr('state', 'is_number') | selectattr('state', 'lt', '20')
             | map(attribute='name') | join(', ') }}
```

**Tuning knob:** threshold (`lt', '20'`), schedule time. This pattern intentionally has **no per-entity condition list to maintain** — it queries the whole state machine by `device_class`, so newly added battery sensors are covered automatically.

### 3j. Phantom-Load / Left-On Watchdog

**Requires:** `sensor` (power, W) on a smart plug or energy-monitoring outlet.
**Fit rationale:** "Fits you because a space heater, iron, or 3D printer left on for hours unattended is both a waste and a fire-risk conversation — catch it on the power draw, not on someone remembering."

```yaml
- id: "printer_left_on_watchdog"
  alias: "3D printer left idle-on watchdog"
  description: "Notifies if the printer's smart plug still draws standby power 30 minutes after the print should have finished (low but nonzero draw)."
  mode: single
  triggers:
    - trigger: numeric_state
      entity_id: sensor.printer_plug_power    # REPLACE
      above: 3                                 # tuning knob: idle-draw watts threshold
      below: 40                                # excludes "actively printing" high draw
      for: "00:30:00"                          # tuning knob: how long is "left on"
  actions:
    - action: notify.mobile_app_blaines_phone    # REPLACE
      data:
        message: "Printer plug has been idle-on for 30 minutes — check if it needs to be shut off."
```

Swap thresholds/entity for any always-plugged appliance (space heater, iron, soldering station). **Gotcha:** pick the `above`/`below` band to bracket the *idle* draw, not zero — a device fully off usually reads near 0W already and won't need a watchdog; the risk case is the appliance staying "on" at low draw indefinitely.

### 3k. Actionable Mobile Notifications

**Requires:** `notify.mobile_app_*`, HA Companion App installed.
**Fit rationale:** "Fits you because a notification you can only read is a chore — one that can act (snooze the alarm, turn off the light, dismiss) closes the loop from your phone."

Full round-trip example: motion notification with "Turn Off Light" / "Ignore" buttons, and a second automation that listens for the button press.

```yaml
# Automation 1: send the actionable notification
- id: "garage_light_left_on_actionable"
  alias: "Garage light left on — actionable notify"
  description: "Notifies with buttons to turn off the garage light or ignore, when it's been on for an hour with nobody home."
  mode: single
  triggers:
    - trigger: state
      entity_id: light.garage    # REPLACE
      to: "on"
      for: "01:00:00"
  conditions:
    - condition: state
      entity_id: person.blaine    # REPLACE
      state: "not_home"
  actions:
    - action: notify.mobile_app_blaines_phone    # REPLACE
      data:
        message: "Garage light has been on for an hour and you're not home."
        data:
          actions:
            - action: "TURN_OFF_GARAGE_LIGHT"
              title: "Turn Off"
            - action: "IGNORE_GARAGE_LIGHT"
              title: "Ignore"

# Automation 2: handle the button press
- id: "garage_light_actionable_response"
  alias: "Garage light notification — handle response"
  description: "Turns off the garage light if the user taps Turn Off on the actionable notification."
  mode: queued
  triggers:
    - trigger: event
      event_type: mobile_app_notification_action
      event_data:
        action: "TURN_OFF_GARAGE_LIGHT"
  actions:
    - action: light.turn_off
      target: { entity_id: light.garage }   # REPLACE
```

**Gotcha:** the `action:` string inside `data.actions` (e.g. `"TURN_OFF_GARAGE_LIGHT"`) must exactly match the `event_data.action` filter in the listening automation's trigger — case-sensitive, no fuzzy matching. Keep these ids UPPER_SNAKE and unique across the whole install to avoid one button firing multiple unrelated automations.

---

## 4. Blueprints

**Prefer a community blueprint when:**
- The pattern is common and well-trodden (motion light, notify-on-open, "leaving home" — all of §3 have popular blueprint equivalents on the HA Community Blueprints Exchange).
- You want a **UI-configurable** automation for a non-technical household member to tweak (blueprints expose `input:` fields as UI form controls — entity pickers, sliders — no YAML editing needed).
- You want to inherit ongoing maintenance/bugfixes from the blueprint author instead of owning the logic yourself.

**Prefer custom YAML (this cookbook) when:**
- The logic needs to reference more than one or two entities in ways a generic blueprint's `input:` schema doesn't anticipate (e.g., combining a lux sensor AND presence AND a schedule helper).
- You want the automation's `id:`/`alias:`/`description:` under your own convention and stored inline in an audited `automations.yaml`, not as a blueprint-instance layer.
- The skill is generating automations programmatically — blueprints add a layer of indirection (`use_blueprint:` + `input:`) that's harder to template safely than the direct action list.

**Import flow (UI):** Settings → Automations & Scenes → Blueprints tab → Import Blueprint → paste the blueprint's URL (raw GitHub link or forum post link) → Home Assistant fetches and adds it to `blueprints/automation/`. Then Settings → Automations & Scenes → Create Automation → pick the imported blueprint → fill in the `input:` fields via the generated UI form → Save (this writes a `- use_blueprint: {path: ..., input: {...}}` entry in `automations.yaml`, still governed by the same `id:` rule in §2).

---

## 5. Testing & Rollback

1. **Config check before anything else.** Developer Tools → YAML → "Check Configuration" (or, scripted: `POST /api/config/core/check_config`) — catches YAML syntax errors before they can break the whole automation platform on reload.
2. **`automation.reload`** — reloads `automations.yaml` (and any packages) without restarting HA. Always call this after a direct file edit; the UI does this automatically on Save.
   ```yaml
   action: automation.reload
   ```
3. **Dry-run with `automation.trigger`.** Runs the automation's action sequence immediately, without waiting for the real trigger to fire.
   ```yaml
   action: automation.trigger
   target: { entity_id: automation.kitchen_motion_light }
   data:
     skip_condition: true   # true = ignore conditions and run actions anyway; false = evaluate conditions first
   ```
   Use `skip_condition: false` to verify the **conditions** are written correctly (does it correctly refuse to run at noon?); use `skip_condition: true` to verify the **actions** are written correctly regardless of current state.
4. **Traces.** Settings → Automations & Scenes → select the automation → Traces (or the trace icon). Shows an interactive graph of the actual run — which trigger fired, which conditions passed/failed, each action's inputs/outputs, and timing. This is the fastest way to see *why* an automation didn't do what you expected — check here before re-reading YAML.
5. **Disable, don't delete, first.** When something's misbehaving: `automation.turn_off` (or the UI toggle) stops it from running while you investigate, without losing the config or its `id:`. Only delete once you've confirmed via traces/dry-run that the automation is wrong in a way worth discarding rather than fixing.
