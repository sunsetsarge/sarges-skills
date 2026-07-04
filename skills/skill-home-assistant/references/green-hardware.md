# Home Assistant Green — Hardware Reference

Verified against home-assistant.io mid-2026. HA ships monthly (Core `2026.M.x`); re-check the Green
product page and the Connect ZBT-2/ZWA-2 pages if this file is more than ~6 months old — radio
firmware and Supervisor terminology both moved in the last cycle (see the Apps rename below).

## What Green is

Home Assistant Green is the "just works" appliance box: **Home Assistant OS preinstalled** →
Supervisor → App store (formerly "Add-on store," renamed **Apps** in Core **2026.2**, Feb 2026 —
expect to see both terms in the wild; the underlying `hassio`/Supervisor mechanics didn't change,
only the label) → one-click full system backups → HACS fully available once installed. Config lives
at `/config` same as any HA OS install (accessible via Samba/File editor app/Studio Code Server app,
or SSH once the SSH app is set up).

**Verified specs:**
- CPU: Rockchip RK3566, quad-core Arm Cortex-A55 @ 1.8 GHz
- RAM: 4 GB LPDDR4X
- Storage: 32 GB eMMC (soldered flash, not swappable — see optimization.md §3 on why recorder bloat
  matters more here than on an SSD-backed install)
- Networking: Gigabit Ethernet (primary — Green has no Wi-Fi radio for its own network connection)
- USB: **two USB 2.0 Type-A ports**, 5V shared up to 2A combined across both — this shared budget
  matters if powering more than one bus-powered stick
- HDMI: diagnostics only, not a general display output
- MicroSD slot: recovery use only, not general storage
- Idle/load power: ~1.7W idle, ~3W under load; passive aluminum heatsink, no fan

## NO built-in radios — Zigbee/Thread/Z-Wave are all add-on sticks

Green ships with zero wireless smart-home radios built in. Every protocol comes from a USB dongle:

### Connect ZBT-2 — Zigbee OR Thread, not both

- Silicon Labs EFR32MG24 Series 2 multiprotocol SoC (same chip family used in HA's ESPHome/Sky
  Connect line), "quadruple the internal speed" of the prior ZBT-1.
- **One protocol at a time by firmware choice.** HA's own guidance: multiprotocol (Zigbee + Thread
  simultaneously) is *theoretically* possible on this hardware but HA **does not plan to implement
  it** — they tested multiprotocol thoroughly on the older Connect ZBT-1 and found it caused device
  stability issues, and the ZBT-2 team is deliberately not repeating that. Flash it as a **Zigbee
  coordinator** (via ZHA or Zigbee2MQTT) or as a **Thread border router** (via the Open Thread Border
  Router app) — pick one per stick. Buy a second ZBT-2 if the house needs both Zigbee and Thread
  border routing from the Green box itself.
- Firmware is managed from the Connect ZBT-2 integration page in HA — Core detects and offers
  updates; you don't need external flashing tools for routine firmware updates.
- **USB-3 interference gotcha — always use the included USB extension cable.** Zigbee/Thread radios
  share the 2.4 GHz band with USB 3.0 signaling noise; a coordinator plugged directly into a port
  next to USB-3 traffic (or directly into a metal-chassis port near an SSD) is a well-documented
  cause of dropped devices and flaky range on Zigbee coordinators generally. On Green specifically
  (USB 2.0 ports only, no internal SSD to worry about) the risk is lower than on a NUC/Pi + SSD combo
  — but still: **use the extension cable, keep the dongle a foot or more away from the Green box
  itself, any powered USB hub, and any other radio-emitting hardware**, rather than dead-plugged into
  the case.

### Connect ZWA-2 — Z-Wave 800-series, long range capable

- **800-series Z-Wave chip**, precisely tuned antenna for range.
- Supports **Z-Wave Long Range (Z-Wave LR)** — same frequency as classic Z-Wave but higher power;
  can run a classic Z-Wave mesh and a Z-Wave LR network simultaneously from the same stick, with
  per-device control over which network a device joins. Tested line-of-sight range ~1.5 km; indoor
  connections commonly 50-100 m horizontally.
- Z-Wave LR is **North America and Europe only** currently, and the device pool supporting it is
  still growing — don't assume every Z-Wave device in the house can join the LR network.
- Same USB-extension-cable gotcha applies — Z-Wave is less 2.4 GHz-noise-sensitive than
  Zigbee/Thread, but keeping it off a hub/away from other USB traffic is still the safe default.
- Managed through the **Z-Wave JS UI** app (see below) — one-click firmware updates and setup wizard
  from there, not a separate flashing tool.

## Mixed-brand reality

A real household network is never one protocol. Expect and plan for:

- **Zigbee (Aqara, Sonoff, etc.)** — pick **ZHA** (built into Core, no extra app, simpler, good
  enough for most single-coordinator households) or **Zigbee2MQTT** (runs as an app + needs
  Mosquitto/MQTT broker, much larger supported-device database and finer per-device tuning, worth it
  once the Zigbee network gets large or has awkward devices ZHA doesn't fully support). Don't run
  both against the same coordinator — pick one path per ZBT-2 stick and commit; migrating later means
  re-pairing every device.
- **Wi-Fi devices** — prefer **Shelly (local API/Gen2+ integration)** and similarly local-first
  brands over cloud-locked Wi-Fi gear. Cloud-brand caveats: devices that only work through a
  manufacturer cloud integration (many budget "smart plug" brands) add a dependency outside HA's and
  the user's control — if the vendor's cloud goes down or the app gets discontinued, the device stops
  responding inside HA too. Flag cloud-only Wi-Fi devices as a resilience gap when found.
- **Z-Wave** via the **Z-Wave JS UI** app (talks to the ZWA-2 stick, exposes a management UI plus the
  actual `zwave_js` integration data to Core).
- **Matter** via the **Matter Server** app — Thread-based Matter devices need a Thread border router
  present on the network (a ZBT-2 flashed to Thread mode, or another Thread border router like an
  Apple TV/HomePod mini/Nest hub already on the LAN) before they'll join reliably; Wi-Fi-based Matter
  devices don't need one.

## Apps essentials for this skill's workflow

Typical Green setup for a serious smart-home instance runs these from the Apps store (Settings →
Apps → Install app, formerly "Add-on store"):

- **Z-Wave JS UI** — if a ZWA-2 (or older Z-Wave stick) is present.
- **Matter Server** — if any Matter devices/Thread border routing is in play.
- **Mosquitto broker** — needed for Zigbee2MQTT and any other MQTT-based integration.
- **File editor** or **Studio Code Server** — in-browser `/config` editing without SSH; Studio Code
  Server is the fuller VS-Code-in-browser experience, File editor is the lighter option.
- **Terminal & SSH** — command-line access to the OS layer (not just `/config`); needed for
  anything beyond what the UI apps expose.

Apps are managed entirely through Supervisor (install/start/stop/update/logs all from the Apps page
per-app) — no separate package manager involved.

## HACS (Home Assistant Community Store)

HACS is the community add-on/integration/theme/Lovelace-card store — **not officially part of Home
Assistant**, maintained by the community, and everything installed through it is third-party code
running with the same trust level as anything else in `/config`.

**Current official install path on HA OS** (verified mid-2026 — no SSH/terminal command needed
anymore for OS installs, this changed from the older `wget | bash` script which is now Container/Core
only):
1. Add the HACS Apps repository to Home Assistant: `https://github.com/hacs/addons` as a
   third-party app repository.
2. Settings → **Apps** → **Install app** → search/select **Get HACS** → Install.
3. Start the app, then check its logs for the remaining setup instructions (GitHub device-code
   auth flow to link HACS to a GitHub account).

**Pin the rule: HACS installs are community code, not vetted HA-core code.** Only install a HACS
integration/card/theme when there's a **concrete, named need** the built-in integration catalog
doesn't cover — not speculatively, not "might be useful later." Every HACS package is one more thing
that can break on a Core update, stop being maintained, or (rarely but not never) carry a supply-chain
risk. Prefer a built-in integration over a HACS equivalent whenever one exists.

## Nabu Casa Cloud (Home Assistant Cloud) — optional

Subscription service from Nabu Casa (HA's commercial arm), **not required** — Green works fully
locally without it. What it adds:
- **Remote access**: reach the instance from outside the LAN without manually configuring port
  forwarding/dynamic DNS/a reverse proxy yourself — encrypted tunnel, simplest way to get phone
  access away from home.
- **Cloud voice**: Nabu's own voice assistant backend, plus the bridge needed to expose HA devices to
  **Google Assistant** and **Amazon Alexa** for voice control through those ecosystems.
- **Cloud backup**: automatic off-box copy of backups (capped 5 GB, most-recent-only) — see
  optimization.md §4; this is the easiest single off-box backup destination but not the only one.
- Also bundles webhook relay and enhanced WebRTC support for camera streaming to remote clients.
- 31-day free trial, then paid monthly/annual.

**Local-first stance**: recommend Nabu Casa only when the household specifically wants remote
access or Alexa/Google voice bridging without self-hosting a tunnel/DDNS setup. Everything else in
this reference (Zigbee, Z-Wave, Matter, Thread, HACS, automations, dashboards) works fully offline
with zero cloud dependency.
