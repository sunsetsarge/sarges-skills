# LibreELEC + Kodi on Raspberry Pi — Imaging, Configuration, Cloning

Verified 2026-07: **LibreELEC 12.2.1** (ships **Kodi 21.3 "Omega"**). Supports Pi 4, Pi 5,
Pi 3, Pi Zero 2 W. Check libreelec.tv/downloads for anything newer before flashing.

## Contents
1. [Why LibreELEC](#1-why-libreelec)
2. [Imaging the SD card](#2-imaging-the-sd-card)
3. [First boot](#3-first-boot)
4. [Adding the Windows share as a source](#4-adding-the-windows-share-as-a-source)
5. [Scrapers, naming, library](#5-scrapers-naming-library)
6. [CEC — TV remote control](#6-cec--tv-remote-control)
7. [Audio](#7-audio)
8. [Network identity per Pi](#8-network-identity-per-pi)
9. [Cloning for additional TVs](#9-cloning-for-additional-tvs)
10. [Shared MySQL library (advanced)](#10-shared-mysql-library-advanced)
11. [Updates](#11-updates)

## 1. Why LibreELEC

Appliance OS: boots directly into Kodi in ~20s, minimal attack/maintenance surface, mostly
read-only filesystem (resists SD-card corruption from power cuts — TVs get unplugged),
auto-updates within its major version. Raspberry Pi OS + Kodi is only worth it if the Pi
must also do non-Kodi work. OSMC is the other appliance option but **still has no Pi 5
support (as of 2026)** — don't recommend it for new builds.

## 2. Imaging the SD card

Preferred — **Raspberry Pi Imager** (raspberrypi.com/software):
1. Choose Device → your Pi model.
2. Choose OS → **Media player OS → LibreELEC** → the entry matching the board.
3. Choose Storage → the microSD (A2-rated, 16–32GB).
4. Write. **Skip the gear-icon/OS-customization screen — it does NOT apply to LibreELEC
   images** (hostname/SSH/Wi-Fi there only work for Raspberry Pi OS). LibreELEC configures
   itself in its own first-boot wizard.

Alternative: LibreELEC's *USB-SD Creator* app, or download the `.img.gz` from
libreelec.tv/downloads/raspberry and flash with Imager's "Use custom".

## 3. First boot

The welcome wizard runs once on the TV:
1. Language/timezone.
2. **Hostname:** name per location — `kodi-livingroom`, `kodi-bedroom`. This is how you'll
   tell the Pis apart forever; don't leave the default.
3. **Network:** join Ethernet (preferred) or Wi-Fi.
4. **SSH: enable it** and set a non-default password when prompted. You will want it for
   maintenance (`ssh root@kodi-livingroom`). Samba (the Pi's own share) can stay off.

## 4. Adding the Windows share as a source

Prereq: `Set-MediaShare.ps1` has run on the PC and printed the path + credentials.

1. Kodi → Settings → Media → Library → **Videos → Add videos…**
2. Browse → **Add network location…** →
   - Protocol: `SMB (Windows network share)`
   - Server name: the PC's hostname (or reserved IP)
   - Shared folder: `Media` (or the share name used)
   - Username / password: the dedicated account (`mediapi` / printed password)
3. Select the new location, name the source (e.g. "Movies"), OK.
4. **Set the content type** (Movies / TV shows) and scraper when prompted — see §5.

Gotchas (both are normal, not bugs):
- **Browsing the network shows nothing:** Kodi's SMB browsing relies on NetBIOS discovery,
  which modern Windows/networks often don't answer. Always *type* the server name — never
  conclude the share is broken because browsing is empty.
- **"Couldn't connect to network server":** Kodi Settings → Services → **SMB client** →
  set *Minimum protocol version* = **SMBv2**, *Maximum* = **SMBv3**, leave "Use legacy
  security" OFF (it's a last-resort toggle; restart Kodi if you change it). Kodi does not
  support SMB1 and Windows shouldn't offer it. On Kodi v20+ these are GUI settings —
  `advancedsettings.xml` editing is no longer needed for SMB protocol pinning.

## 5. Scrapers, naming, library

Scrapers: **TMDB** for movies, **TVDB** (or TMDB TV) for shows — set per source when
choosing content type. They fetch artwork, plots, cast.

Naming conventions the scrapers require — fix names BEFORE the first scan:

```
Media/
├── Movies/
│   ├── Heat (1995).mkv
│   └── The Iron Giant (1999)/The Iron Giant (1999).mkv     # folder-per-movie also fine
└── TV/
    └── Band of Brothers/
        └── Season 01/
            ├── Band of Brothers S01E01.mkv
            └── Band of Brothers S01E02.mkv
```

Rules: year in parentheses for movies; `S01E01` episode markers; one show per folder,
`Season NN` subfolders. Misnamed files scrape wrong or not at all, and repairing a
polluted library DB is far more work than renaming up front.

Library refresh under architecture A is per-Pi: enable Settings → Media → Library →
"Update library on startup", or trigger from another device via Kodi's web interface
(Settings → Services → Control → Allow remote control via HTTP).

## 6. CEC — TV remote control

CEC lets the TV's own remote drive Kodi over the HDMI cable. On LibreELEC it works out of
the box — *if* the TV side is on. Every brand hides CEC under its own name:

| Brand | CEC trade name |
|---|---|
| Samsung | Anynet+ |
| Sony | Bravia Sync |
| LG | SimpLink |
| Panasonic | Viera Link |
| Philips | EasyLink |
| Toshiba | Regza Link |

Enable it in the TV's settings menu, then reboot the Pi with the TV on.

**Pi 5:** CEC only works on the **HDMI port nearest the USB-C power connector** (HDMI0) —
kernel-level, not fixable in settings. Plug the TV into that port. (Pi 4: either port
works.) If Kodi shows duplicate "CEC Adapter" peripherals on a Pi 5, that's the same
device seen twice — harmless.

Test CEC **before** mounting the Pi behind the TV. Fallbacks if a TV's CEC is broken: the
Kore phone app (official Kodi remote), a cheap 2.4GHz air-mouse, or a Flirc USB IR receiver.

## 7. Audio

- TV speakers over HDMI: default config, nothing to do.
- AVR/soundbar that decodes DD/DTS: Settings → System → Audio → *Allow passthrough* ON,
  enable the codecs the AVR supports; set channels to match. If dialogue is silent but
  menus click, passthrough is sending a codec the device can't decode — trim the enabled
  list.
- Lip-sync drift: adjust per-file with the audio-offset dial (video OSD) or globally in
  audio settings.

## 8. Network identity per Pi

- Hostname set in the wizard (§3) — change later at Settings → LibreELEC → Network.
- **DHCP reservation per Pi** in the router (and one for the PC). Stable IPs keep `ssh`,
  Kore, and any HTTP control endpoints from silently breaking.
- Record each unit in a table the user keeps with the router docs:

| Location | Hostname | Reserved IP | MAC | Notes |
|---|---|---|---|---|
| Living room | kodi-livingroom | 10.10.1.21 | … | Pi 4 4GB, wired |

## 9. Cloning for additional TVs

Build the FIRST Pi completely (share, scrapers, CEC, audio, settings), then clone:

1. Shut the Pi down, pull the SD card.
2. On the PC, image the whole card to a file (Win32 Disk Imager, or
   `dd` from WSL: `dd if=\\.\PhysicalDriveN of=kodi-golden.img bs=4M`). Keep
   `kodi-golden.img` — it's the golden image for every future TV and the disaster-recovery
   backup.
3. Write the image to a new card (Raspberry Pi Imager → "Use custom" → the .img).
4. Boot the new card in the new Pi, then change ONLY:
   - Hostname (Settings → LibreELEC → Network) — e.g. `kodi-bedroom`.
   - Add the new MAC's DHCP reservation; add the table row.
5. Kodi's library DB rides along in the clone — the new TV starts fully configured.

Same-model boards clone cleanly (Pi 4 image → Pi 4). A Pi 4 image also boots a Pi 5 under
current LibreELEC, but flash the Pi-5-specific image for new Pi 5 units instead.
Re-imaging an existing TV's card from the golden image is also the fastest fix for a
corrupted card — another reason media never lives on the Pi.

## 10. Shared MySQL library (advanced)

Sync watched/resume state across Pis without a media server. See
[architecture-comparison.md](architecture-comparison.md) §A+ for whether to do this at all.

1. Install MariaDB (≥10.2.5) on the always-on PC; create a `kodi` user with its own
   password and grant it rights to create databases (Kodi creates `MyVideos*`/`MyMusic*`
   schemas itself). Open TCP 3306 on the Private firewall profile only.
2. On EACH Pi, create `/storage/.kodi/userdata/advancedsettings.xml` (via SSH):

```xml
<advancedsettings>
  <videodatabase>
    <type>mysql</type>
    <host>PC-HOSTNAME-OR-IP</host>
    <port>3306</port>
    <user>kodi</user>
    <pass>THE_PASSWORD</pass>
  </videodatabase>
  <videolibrary>
    <importwatchedstate>true</importwatchedstate>
    <importresumepoint>true</importresumepoint>
  </videolibrary>
</advancedsettings>
```

3. One Pi scans the library once; all others see it immediately. Media still streams over
   the SMB share; per-Pi paths must be identical (they are, when cloned).
4. **Version discipline:** all Kodi instances must be the same major version — a shared-DB
   Kodi upgrade migrates the schema and strands older clients. Pin/coordinate LibreELEC
   major updates. Reference: kodi.wiki/view/MySQL.

## 11. Updates

- LibreELEC auto-updates within the major version (Settings → LibreELEC → System →
  Updates). Major-version jumps: check the libreelec.tv blog first, and if running the
  shared-DB setup, update all Pis together (refresh the golden image afterwards).
- Kodi version rides with LibreELEC — never update Kodi separately on LibreELEC.
