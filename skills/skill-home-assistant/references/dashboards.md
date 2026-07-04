# Home Assistant Dashboards — Reference

Verified against live docs 2026-07-04: `home-assistant.io/dashboards/` (views, sections, tile, heading,
grid, cards overview). Schema below reflects the **current Sections layout**, the default view type
for new dashboards since HA introduced it — masonry is legacy-default, not modern-default.

## Table of contents

1. [Storage mode vs YAML mode](#1-storage-mode-vs-yaml-mode)
2. [The Sections view layout](#2-the-sections-view-layout)
3. [Mobile-first rules](#3-mobile-first-rules)
4. [Built-in card catalog](#4-built-in-card-catalog-mapped-to-entity-domains)
5. [HACS cards (upgrade-only)](#5-hacs-cards-upgrade-only-confirm-installed-first)
6. [Theming](#6-theming)
7. [Propose → confirm → implement → validate procedure](#7-propose--confirm--implement--validate-procedure)

---

## 1. Storage mode vs YAML mode

Home Assistant dashboards persist one of two ways:

- **Storage mode** (default for any dashboard created in the UI): config lives in `.storage/lovelace*`,
  edited live through Settings → Dashboards or the pencil/edit-dashboard UI. Multiple dashboards, each
  its own storage key. **This skill defaults to storage mode.**
- **YAML mode**: `lovelace: mode: yaml` in `configuration.yaml`, config lives in `ui-lovelace.yaml`
  (or per-dashboard files), hand-edited, requires a HA restart or YAML reload to take effect, UI editor
  is read-only in this mode.

**Why this skill defaults to storage mode:**

- The user can still tweak things by hand in the app without touching a file or SSH.
- It's inspectable and mutable over the **WebSocket API** (`lovelace/config/save`,
  `lovelace/config/get`) — this skill talks to a running HA instance, not a file on disk, so storage
  mode is the only mode it can safely read-modify-write without a restart.
- YAML mode is a deliberate opt-in for users who want dashboards in version control. If the user's
  instance is already in YAML mode, treat that as an explicit signal — write the file, note that a
  reload/restart is required, and do not attempt to flip them to storage mode.

**Never blind-overwrite.** Every dashboard write in storage mode follows read-merge-write:

1. `lovelace/config/get` (with the target `url_path`, or omit for the default dashboard) to pull the
   **current** config.
2. Merge the new/changed view into `views: []` — append if the view (`path`) doesn't exist, replace
   just that one element if it does. Never touch sibling views.
3. `lovelace/config/save` with the full merged config (the API replaces the whole dashboard config in
   one shot — there is no partial-view "patch" endpoint).
4. `lovelace/config/get` again immediately after, and diff mentally against what was intended, before
   telling the user it's done.

If the target dashboard doesn't exist yet, create it as its own storage-mode dashboard (`lovelace/
config/save` against a new `url_path`) rather than piling everything into the auto-generated default
dashboard — keeps a bad write blast-radius to one dashboard.

---

## 2. The Sections view layout

`type: sections` is the modern default: a CSS-grid-like layout where **sections are boxes on a grid**,
each section holds a vertical stack of cards, and the browser reflows sections responsively (columns
collapse to 1 on narrow/mobile viewports automatically — no manual breakpoint config needed).

### View-level keys

```yaml
views:
  - type: sections
    title: Home
    path: home                 # REPLACE: URL slug, defaults to view index if omitted
    icon: mdi:home
    theme: default              # optional theme override for this view only
    max_columns: 4              # optional; caps how many section-columns can appear side by side
    subview: false              # true = hide from the nav tab strip (used for area drill-downs)
    badges:                     # view-level badges, rendered above all sections
      - entity: person.PLACEHOLDER_owner   # REPLACE
    header:
      layout: center             # start | center | responsive
      badges_position: bottom    # bottom | top
    sections:
      - type: grid
        title: Living Room        # optional section heading text
        column_span: 2            # how many grid columns this section spans (default 1)
        cards:
          - type: heading
            heading: Living Room
            icon: mdi:sofa
          - type: tile
            entity: light.PLACEHOLDER_living_room_lamp   # REPLACE
        visibility:                # optional — hide the whole section conditionally
          - condition: state
            entity: input_boolean.PLACEHOLDER_show_advanced   # REPLACE
            state: "on"
```

Key points confirmed against current docs:

- **`sections` is a list of grid boxes**, each `type: grid` (this is the only section type). Each
  section has its own `cards:` list, an optional `title`, an optional `column_span` (how wide the box
  is, default `1`), and an optional `row_span`.
- **`heading` cards** are the idiomatic way to label a group of tiles inside a section (instead of the
  section's own `title`, which renders differently) — `type: heading`, `heading:`, `heading_style:
  title|subtitle`, optional `icon`, and optional `badges:` (entity or button badges) attached directly
  to the heading row. Use a heading card when you want per-group badges; use the section's own `title`
  for a plain label.
- **`header`** is view-wide (sits above all sections): `layout` controls alignment of the title/badge
  row, `badges_position` controls whether badges sit above or below the header card/title.
- **`visibility`** conditions can be attached to a whole section (hide the box) or to individual cards
  inside it (same `condition:` block syntax used elsewhere in HA — `state`, `numeric_state`, `screen`,
  `user`, etc.).
- **`background`** can be set per-section (`background: true` for the theme default, or `{color: "...",
  opacity: 80}` for a custom one) — light-touch use only, don't decorate every section.
- **Per-card `grid_options`**: individual cards inside a section can carry their own `grid_options:
  {columns: N, rows: N}` to influence how much of the section's internal grid they occupy — this is
  distinct from the section-level `column_span`. In the UI this is exposed as the card's resize handles
  in "Layout" edit mode. Don't hand-author exotic multi-row spans; let tile/heading cards use their
  natural size unless the user specifically asks for a denser layout.

### A complete, valid example view

```yaml
- type: sections
  title: Downstairs
  path: downstairs
  icon: mdi:floor-plan
  badges:
    - entity: weather.PLACEHOLDER_home            # REPLACE
    - entity: binary_sensor.PLACEHOLDER_anyone_home # REPLACE
  sections:
    - type: grid
      title: Kitchen
      cards:
        - type: heading
          heading: Kitchen
          icon: mdi:countertops
        - type: tile
          entity: light.PLACEHOLDER_kitchen_main   # REPLACE
        - type: tile
          entity: switch.PLACEHOLDER_kitchen_fan    # REPLACE
    - type: grid
      title: Living Room
      cards:
        - type: heading
          heading: Living Room
          icon: mdi:sofa
        - type: tile
          entity: light.PLACEHOLDER_living_room_lamp  # REPLACE
        - type: thermostat
          entity: climate.PLACEHOLDER_living_room     # REPLACE
```

---

## 3. Mobile-first rules

The HA companion app and phone browsers are the primary surface for most households — design for one
column first, desktop is the reflow bonus, not the target.

- **One-column-friendly sections**: keep each section's card count small (3-6 tiles) so it reads
  cleanly when sections stack to a single column on a phone. Don't build a 12-card mega-section
  expecting a wide desktop grid — it becomes an unreadable scroll wall on mobile.
- **Most-used controls at the top**: order sections so the things touched daily (main lights, front
  door lock/camera, thermostat) are in the first section(s) of the view, not buried under "nice to
  glance at" sensors.
- **Tap targets**: prefer **tile cards over entity-rows** for anything the user actually presses. Tile
  cards render as large touch-friendly boxes with a toggle built in; the classic `entities` card renders
  compact rows meant for glancing/reading, with small tap targets — fine for read-only sensor lists, bad
  for "toggle this light with my thumb."
  - Toggle-heavy area → tiles.
  - Long list of sensors to skim → `entities` or `sensor`/`history-graph`.
- **Per-view icons**: give every view an `icon:` — the nav strip on mobile becomes icon-only when there
  are more views than fit, so a missing icon means an unlabeled blank tab.
- **Badges for glanceable state**: use view-level or heading-level badges (weather, presence, alarm
  state, key binary sensors) so status is visible without opening a section — badges are the mobile
  equivalent of a status bar.

---

## 4. Built-in card catalog mapped to entity domains

Built-in cards first, always — reach for a HACS card only when a built-in card genuinely can't do the
job (see section 5). Default to **tile** for anything not covered by a domain-specific card below.

| Domain / use case | Card | When to use | Minimal YAML |
|---|---|---|---|
| Generic entity, any domain | `tile` | Default workhorse — toggles, sensors, covers, locks, anything with one primary state | `type: tile`<br>`entity: light.PLACEHOLDER` |
| `light.*` | `light` | Only when you want the full brightness-slider + color-wheel popup inline (not just a toggle) — otherwise use tile | `type: light`<br>`entity: light.PLACEHOLDER` |
| `climate.*` | `thermostat` | Full round dial with current/target temp and HVAC mode — better than tile when climate control is a primary task for that view | `type: thermostat`<br>`entity: climate.PLACEHOLDER` |
| `humidifier.*` | `humidifier` | Dehumidifier/humidifier control, same rationale as thermostat | `type: humidifier`<br>`entity: humidifier.PLACEHOLDER` |
| `media_player.*` | `media-control` | Full transport controls + volume + artwork | `type: media-control`<br>`entity: media_player.PLACEHOLDER` |
| `camera.*` (live feed + basic controls) | `picture-glance` | Live snapshot with a small row of entity icons/toggles overlaid (e.g. camera + attached light + lock) | `type: picture-glance`<br>`camera_image: camera.PLACEHOLDER`<br>`entities:`<br>`  - light.PLACEHOLDER_porch` |
| `camera.*` (feed only, no controls) | `picture-entity` | Just the image/stream, tap to open more-info | `type: picture-entity`<br>`entity: camera.PLACEHOLDER` |
| `weather.*` | `weather-forecast` | Current conditions + forecast strip | `type: weather-forecast`<br>`entity: weather.PLACEHOLDER` |
| Energy dashboard data | `energy-*` (energy-distribution, energy-date-selection, energy-sources-table, etc.) | Only inside a view backed by the Energy dashboard config — these read from long-term statistics, not a single entity | `type: energy-distribution`<br>`link_dashboard: true` |
| Historical trend of one/more sensors | `history-graph` | Line/state history over a chosen period | `type: history-graph`<br>`entities:`<br>`  - sensor.PLACEHOLDER_temp` |
| Single numeric value as a dial | `gauge` | Battery %, humidity %, load % — anything with a natural min/max | `type: gauge`<br>`entity: sensor.PLACEHOLDER_battery`<br>`min: 0`<br>`max: 100` |
| Single sensor with sparkline | `sensor` | Compact numeric readout + mini trend line, lighter than history-graph | `type: sensor`<br>`entity: sensor.PLACEHOLDER_outdoor_temp` |
| `todo.*` | `todo-list` | Shopping/task lists backed by a to-do integration | `type: todo-list`<br>`entity: todo.PLACEHOLDER_groceries` |
| `alarm_control_panel.*` | `alarm-panel` | Arm/disarm keypad | `type: alarm-panel`<br>`entity: alarm_control_panel.PLACEHOLDER` |
| An Area (device group) | `area` | One card that surfaces an Area's camera/climate/lights/sensors summary without hand-listing every entity | `type: area`<br>`area: PLACEHOLDER_living_room` |
| `device_tracker.*` / zones | `map` | Person/device location on a map | `type: map`<br>`entities:`<br>`  - person.PLACEHOLDER_owner` |
| Section/group label | `heading` | Groups tiles under a labeled, iconified row inside a section (see §2) | `type: heading`<br>`heading: PLACEHOLDER Kitchen` |

---

## 5. HACS cards (upgrade-only — confirm installed first)

**Rule: never assume HACS is present.** Before proposing any card below, check the frontend resources
(`lovelace/resources/list` over the WebSocket API, or ask the user) for the corresponding
`www/community/...` resource. If it isn't registered, either the built-in equivalent from section 4 is
the answer, or the response is "this needs HACS + card X installed first" — never silently degrade to
inventing YAML for a card that won't render.

| Card | What it adds over built-in |
|---|---|
| **Mushroom** | Full component library (mushroom-light-card, mushroom-climate-card, mushroom-chips-card, etc.) with more compact, more configurable, more theme-consistent styling than tile — the most common "why does my dashboard look prettier than default HA" answer |
| **mini-graph-card** | Compact multi-entity sparkline/line-graph, denser and more configurable than the built-in `sensor`/`history-graph` cards (multiple lines, fill, smoothing) |
| **ApexCharts card** | Full charting library — bar/line/area with aggregation, multi-axis, long time ranges; use when history-graph/statistics-graph can't express the query |
| **auto-entities** | Meta-card: generates a card's entity list dynamically from a filter (by area, by state, by attribute) instead of hand-listing entity_ids — huge win for "show me every light that's currently on" style views that should stay correct as entities are added/removed |
| **card-mod** | Injects raw CSS into any card — use only for a specific visual ask (e.g. "make this tile red when open") that themes/color options can't reach |
| **bubble-card** | Pop-up/slide style cards (bubble pop-up, bubble button) — alternate control aesthetic, similar territory to Mushroom |
| **button-card** | Extremely configurable custom button/tile replacement with templated icon/color/text — reach for it only when tile + card-mod still can't express the visual, since it has the steepest config curve of this list |

Minimal example — **Mushroom** (light entity, after confirming Mushroom cards are installed):

```yaml
- type: custom:mushroom-light-card
  entity: light.PLACEHOLDER_living_room_lamp   # REPLACE
  show_brightness_control: true
  show_color_control: false
```

Minimal example — **auto-entities** (all lights currently on, after confirming it's installed):

```yaml
- type: custom:auto-entities
  card:
    type: entities
    title: Lights On
  filter:
    include:
      - domain: light
        state: "on"
```

---

## 6. Theming

Keep a light touch — most households never need more than "pick a built-in theme, maybe force dark
mode." Don't build custom theme YAML unless asked.

- HA ships built-in themes (`default`, plus any bundled with installed integrations/frontend). Assign
  per-dashboard or per-view with `theme: <name>` in the view/dashboard config (see §2 example).
- `frontend.set_theme` service call switches the active theme for a user session at runtime — useful
  for an automation-driven day/night theme swap, not something to wire into a static dashboard file.
- Dark mode: users can force it in their profile (Settings → profile → "Dark mode": always). Don't
  hardcode a dark theme into a shared dashboard unless the whole household wants it — prefer leaving
  theme as `default` and letting each user's profile decide, since Sections view already respects the
  system/profile light-dark toggle.

---

## 7. Propose → confirm → implement → validate procedure

Every dashboard change this skill makes follows this loop — never invent an `entity_id`, always read
the live registry first.

1. **Gather real IDs.** Pull the current area/entity/device registry (`config/area_registry/list`,
   `config/entity_registry/list`, or equivalent) for the area(s)/domain(s) in scope. Only entity_ids
   that exist in that pull are eligible to appear in generated YAML — no guessing at plausible-looking
   ids like `light.living_room_lamp` without confirming it's real.
2. **Propose in plain language first.** Before writing YAML, describe the structure to the user: "a new
   'Living Room' section with a heading, then tiles for these 4 entities: [list], plus a thermostat
   card for climate.living_room" — let them catch a wrong entity or missing device before YAML exists.
3. **Generate the YAML** from the confirmed structure and registry-verified ids, following section 2's
   Sections schema.
4. **Confirm** the exact YAML (or its plain-language shape, for a non-technical user) before writing.
5. **Implement**: `lovelace/config/get` → merge the new/changed view in → `lovelace/config/save`, per
   the read-merge-write rule in section 1. Never target a raw file when the instance is in storage mode.
6. **Validate**: `lovelace/config/get` again immediately after save, confirm the view/section/cards
   landed as intended (right entity_ids, right card types, nothing else in the config changed), and
   only then report success back to the user.
