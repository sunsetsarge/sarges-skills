---
name: skill-rpi-media-player
description: >-
  Design, build, and maintain a Raspberry Pi home media playback system — one Pi per TV,
  playing video files stored on a Windows PC over the LAN, with a couch Kodi UI and TV-remote
  (HDMI-CEC) control — OR one Pi as a headless Plex SERVER feeding Apple TV / Infuse /
  smart-TV clients. Guides the architecture choice (LibreELEC+Kodi vs Jellyfin vs Plex vs
  Pi-as-server), picks the board (Pi 4 vs Pi 5 decode), ships a one-action PowerShell script
  for a secure read-only Windows SMB share, and covers imaging, Kodi setup, multi-TV cloning,
  and troubleshooting. USE THIS SKILL whenever the user mentions: raspberry pi media player,
  pi 4, pi 5, kodi, libreelec, osmc, jellyfin, plex, media server, HTPC, apple tv, infuse,
  stream video to a TV, SMB share, NFS, DLNA, CEC, or cord-cutting with their own files —
  even without saying "media player" ("watch my PC videos on the living-room TV", "add
  another TV"). Also maintenance: SMB browse failures, home videos choppy/won't play
  (VFR/HEVC), stutter, watched-state sync.
---

# Raspberry Pi Media Player Builder

Take the user from zero (no Pi purchased) to one-or-more Raspberry Pis playing video files
stored on their Windows PC, with TV-remote control. This is a decision-guiding skill: ask
first, then branch, and load only the reference file for the chosen path.

Facts in this skill were verified 2026-07 (LibreELEC 12.2.1 / Kodi 21.3 "Omega",
Jellyfin 10.11.11). Versions drift — if a download page shows something newer, prefer the
current stable and re-verify any claim that sounds version-specific.

## Step 0 — Ask before branching

Ask these four questions FIRST (one message, all four). The answers pick the architecture
and the hardware — do not recommend anything before you have them:

1. **How many TVs**, now and realistically later?
2. **1080p or 4K?** (TV resolution AND whether the library has 4K/high-bitrate files)
3. **Ethernet or Wi-Fi at each TV location?** (changes hardware + codec advice: wired is
   strongly preferred for 4K/high-bitrate; Wi-Fi is usually fine for 1080p)
4. **Cross-TV resume/watched sync wanted?** ("pause in the living room, resume in the
   bedroom") — this is the main reason to choose Jellyfin over plain Kodi.

Also get: the **exact Windows folder path** of the video library, and whether the PC runs
**Windows Home or Pro** (Pro on 24H2 enforces SMB signing — the share script's dedicated
account handles it, but guest access is a dead end there).

## Step 1 — Pick the architecture

Full matrix: [references/architecture-comparison.md](references/architecture-comparison.md).
Short version:

| | A — LibreELEC + Kodi, direct SMB | B — Jellyfin server + Kodi/Jellyfin clients | C — Plex |
|---|---|---|---|
| PC-side software | none (just a share) | Jellyfin Server (Windows) | Plex Media Server |
| Watched/resume sync across TVs | no (per-Pi), unless MySQL DB added | **yes, built-in** | yes |
| Remote/off-network access | no | yes, free | paywalled (2025+) |
| Setup effort | lowest | medium | medium |
| **Default when…** | **1–3 TVs, no sync needed** | many TVs or sync/remote wanted | user already owns Plex Pass |

- **Default = A** for a couple of TVs. Most bulletproof: nothing to keep running on the PC
  except the share.
- **Choose B** if the user answered yes to cross-TV sync or wants phone/remote access.
  Jellyfin direct-plays to Pi clients (no transcoding load on the PC for normal H.264/HEVC
  files).
- **C (Plex)** only if they're invested in it: remote streaming is paywalled since April
  2025 and the Pi/Kodi client story is weak. Same shape as B otherwise.
- **A + shared MySQL/MariaDB library DB** is the "sync without a media server" advanced
  path — documented in the LibreELEC reference. Offer it only to users comfortable running
  a database; Jellyfin is easier for the same outcome.
- **D — Pi as headless Plex SERVER, TVs bring their own player (Apple TV/Infuse, sticks,
  smart TVs).** When the TVs already have good players, invert the whole design: don't put
  a Pi at each TV — one Pi + USB drive serves the house, the TV devices decode. Golden rule:
  the Pi must NEVER transcode. Full build/maintenance/VFR-home-video playbook:
  [references/plex-server-appletv.md](references/plex-server-appletv.md). Proven live 2026-07.

## Step 2 — Pick the hardware (one Pi per TV)

- **Default board: Raspberry Pi 4 (2GB is enough; 4GB comfortable).** It has hardware
  H.264 decode (1080p60) AND hardware HEVC decode (4Kp60) — the safe choice for a mixed
  library.
- **Pi 5 caveat (verified): the Pi 5 has NO hardware H.264 decoder** — H.264 is
  software-decoded on the CPU. That's fine at 1080p (the A76 cores keep up easily) but
  high-bitrate/4K H.264 can strain it, and most personal libraries are H.264-heavy. Pi 5
  only makes sense if the library is mostly HEVC or the user wants the Pi for other duties.
  Pi 5 also needs a 5V/5A PSU and its CEC only works on the HDMI port nearest the USB-C
  power connector.
- **Budget 1080p-only:** Pi 3 or Pi Zero 2 W work but skip 4K.
- **Per-Pi shopping list:** board + official PSU (Pi 4 = 5V/3A USB-C, Pi 5 = 5V/5A) +
  A2-rated 16–32GB microSD (OS only — media stays on the PC) + **micro-HDMI→HDMI cable**
  (both boards use micro-HDMI; people always forget this) + case with heatsink/fan (bare
  boards throttle on sustained playback) + Ethernet cable if wired.

## Step 3 — Windows PC setup (one action)

For architecture A (and as the media source for B if Jellyfin reads the same folders):
run the bundled script **as Administrator**:

```powershell
.\scripts\Set-MediaShare.ps1 -MediaPath "D:\Videos"            # defaults: share 'Media', user 'mediapi'
.\scripts\Set-MediaShare.ps1 -MediaPath "D:\Videos" -WhatIf    # dry run first
```

In one idempotent action it: creates/reuses a dedicated **read-only local account**
(never the user's own login), creates the SMB share with read-only access over SMBv2/v3
(SMB1 is never enabled — Kodi doesn't support it and neither should Windows), opens the
firewall for SMB **on the Private profile only**, and prints the exact `\\PC\Media`,
`smb://PC/Media`, and IP-based paths plus the credentials to type into Kodi. Details,
manual steps, DHCP-reservation guidance, and Home-vs-Pro quirks:
[references/windows-share-setup.md](references/windows-share-setup.md).

For architecture B, additionally follow [references/jellyfin.md](references/jellyfin.md)
(server install, libraries, hardware transcoding via Intel QSV / NVIDIA NVENC).

## Step 4 — Image and configure the Pi

Follow [references/libreelec-kodi.md](references/libreelec-kodi.md). Outline:

1. **LibreELEC**, not Raspberry Pi OS + Kodi: boots straight into Kodi, mostly read-only
   FS (survives power cuts / resists SD corruption), auto-updates. Flash with Raspberry Pi
   Imager → *Choose OS → Media player OS → LibreELEC* (note: Imager's hostname/SSH
   customization does NOT apply to LibreELEC images — use LibreELEC's first-boot wizard).
2. First-boot wizard: set per-TV hostname (`kodi-livingroom`), enable SSH, join network.
3. Add the media source (`smb://…` + the mediapi credentials), set content type, scrapers
   (TMDB movies / TVDB shows), **enable CEC** so the TV remote drives Kodi (Samsung
   Anynet+, Sony Bravia Sync, LG SimpLink, Panasonic Viera Link — it must be ON in the TV
   menu too), audio passthrough if there's an AVR.
4. Give each Pi a DHCP reservation in the router, and one for the PC (stable paths).

File naming the scrapers need (get this right BEFORE the first scan):
`Movies/Movie Title (2004).mkv` and `TV/Show Name/Season 01/Show Name S01E03.mkv`.

## Step 5 — Multi-TV scaling

Image and configure ONE Pi completely, then clone its SD card for each additional TV and
change only the hostname (+ new DHCP reservation). Keep a per-Pi table (location /
hostname / IP / MAC). Under B all Pis point at the one Jellyfin server and state syncs;
under A accept per-Pi libraries or add the MySQL shared DB. Clone procedure:
[references/libreelec-kodi.md](references/libreelec-kodi.md) §Cloning.

## Codec reality check

Before buying hardware, sample the library:
`ffprobe -v error -select_streams v:0 -show_entries stream=codec_name,width,bit_rate file.mkv`
(or MediaInfo). Map: H.264 1080p → any board; HEVC/4K → Pi 4 or Pi 5; **H.264 4K/high-bitrate
→ Pi 4 only** (Pi 5 software decode may stutter); AV1 → Pi 5 handles 1080p in software, no
hardware decode on either. High-bitrate 4K over Wi-Fi will stutter regardless of board — wire it.

## Hard-Won Rules

1. **Pi 5 is not "Pi 4 but faster" for this job** — it dropped the H.264 hardware decoder.
   For an H.264-heavy library the older Pi 4 is the better media player. Verified 2026-07.
2. **Never SMB1, anywhere.** Kodi doesn't support it; Windows shouldn't have it. If Kodi
   won't browse the share, fix protocol/auth (Kodi Settings → Services → SMB client →
   min SMBv2 / max SMBv3), don't downgrade security.
3. **Windows 11 24H2 Pro enforces SMB signing → guest/anonymous shares silently fail**
   from Linux clients. Always use the dedicated local account; never rely on guest access,
   and never use Blaine's real login for a share credential.
4. **Kodi browsing (`smb://` in the file dialog) uses NetBIOS discovery and often shows
   nothing on modern networks.** Type the full path manually (server-name or IP). Not a
   firewall bug; don't chase it.
5. **Imager's gear-icon customization silently does nothing for LibreELEC** — hostname and
   SSH are set in LibreELEC's own first-boot wizard. Don't tell the user to pre-configure.
6. **CEC on Pi 5 only works on the HDMI port next to the USB-C power connector.** On any
   Pi, CEC must also be enabled in the TV's own menu (each brand hides it under its trade
   name). Test CEC before mounting the Pi behind the TV.
7. **Name files before the first library scan.** Fixing names after a bad scrape means
   cleaning the library DB — 10× the work of renaming up front.
8. **Media stays on the PC; the SD card is disposable.** Never store videos on the Pi.
   Any SD corruption is then a 10-minute reflash, and cloning stays trivial.
9. **Wire anything 4K.** Wi-Fi "works in testing" then stutters at 9 PM when the
   neighborhood spectrum is busy. If Ethernet can't reach, prefer 5GHz + lower-bitrate
   files, or MoCA/powerline before blaming the Pi.
10. **DHCP reservations for the PC and every Pi, day one.** Sources break when the PC's
    IP changes; SSH runbooks break when the Pi's does.
11. **Shared MySQL DB requires every Kodi to be the same major version** — one auto-updated
    Pi can orphan the others. If the user wants sync, steer to Jellyfin unless they'll
    pin versions.
12. **Direct-play means the PC does near-zero work under Jellyfin** for H.264/HEVC files a
    Pi can decode. If the PC fans spin up during playback, something is transcoding —
    find out why (usually subtitles burn-in or an exotic codec), don't buy a GPU first.
13. **"Movies play fine but home videos don't" = a transcode problem, always.** Phone
    footage is HEVC + variable-frame-rate and forces server transcodes a Pi can't do
    (no HEVC encoder). Fix by re-encoding to CFR H.264 on a real PC — recipe in
    [references/plex-server-appletv.md](references/plex-server-appletv.md) §4.
14. **In the server topology (D), the Pi must never transcode or analyze** — disable
    Plex's BIF/intro/credits/loudness/deep-analysis generators, use Infuse as the player,
    and do any re-encoding on an x86 box. `vcgencmd get_throttled ≠ 0x0` on a serve-only
    Pi means a hidden job is violating this.

## Maintenance

- **Add a TV:** clone SD → new hostname → DHCP reservation → table row. ~15 minutes.
- **Updates:** LibreELEC auto-updates within its major version; check libreelec.tv before
  major jumps. Jellyfin server updates via installer; update the Kodi add-on in step.
- **Something broke:** [references/troubleshooting.md](references/troubleshooting.md) —
  organized by symptom (can't browse share / auth fails / stutter / no CEC / library mess).
- **Re-run `Set-MediaShare.ps1` any time** — it's idempotent and will repair share, ACL,
  account, and firewall drift, and re-print the connection info.
