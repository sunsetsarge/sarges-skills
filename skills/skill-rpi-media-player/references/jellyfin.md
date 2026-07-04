# Jellyfin — Centralized Library with Cross-TV Sync (Architecture B)

Verified 2026-07: **Jellyfin Server 10.11.x** stable (10.11.11 current; 12.0 in RC —
prefer the stable line). Free and open-source; jellyfin.org/downloads.

## Contents
1. [Server install (Windows)](#1-server-install-windows)
2. [Libraries and scan settings](#2-libraries-and-scan-settings)
3. [Hardware transcoding](#3-hardware-transcoding)
4. [Pi client: Jellyfin for Kodi vs JellyCon](#4-pi-client-jellyfin-for-kodi-vs-jellycon)
5. [Direct play — why the PC stays idle](#5-direct-play--why-the-pc-stays-idle)
6. [Users, sync, remote access](#6-users-sync-remote-access)
7. [Updates](#7-updates)

## 1. Server install (Windows)

1. Download the **Windows installer (.exe)** from jellyfin.org/downloads/server (a
   portable ZIP also exists; the installer sets up the Windows service — use it).
2. Install as a **Windows service** with automatic start, so playback doesn't depend on
   anyone being logged in.
3. First-run wizard at `http://localhost:8096`: create the admin account, add libraries
   (§2), skip remote access for now (§6).
4. The server reads the media folders directly from disk (`D:\Videos\Movies`) — it does
   NOT need the SMB share. Keep the share anyway if any Pi runs plain-Kodi (arch A) or as
   the path for adding files from other machines.
5. Firewall: the installer/first-run normally opens TCP 8096. Verify:
   `Get-NetFirewallRule | Where-Object DisplayName -like '*Jellyfin*'` — the rule should
   be enabled for the **Private** profile. If missing:
   `New-NetFirewallRule -DisplayName 'Jellyfin HTTP' -Direction Inbound -Protocol TCP -LocalPort 8096 -Profile Private -Action Allow`
6. Give the PC a DHCP reservation — every client will be pointed at this address.

## 2. Libraries and scan settings

Dashboard → Libraries → Add Media Library:
- Content type **Movies** → folder `…\Movies`; content type **Shows** → folder `…\TV`.
  Same naming conventions as Kodi scrapers (`Title (Year)`, `Show/Season 01/Show S01E01`).
- Metadata downloaders: TheMovieDb for movies, TheTVDB/TheMovieDb for shows (defaults are
  fine). Prefer embedded/local images ON if .nfo/artwork already exist alongside files.
- Enable **real-time monitoring** so new files appear without manual scans, and schedule a
  nightly library scan as backstop (Dashboard → Scheduled Tasks).

## 3. Hardware transcoding

Usually idle (see §5) but cheap insurance for remote streams and subtitle burn-in.
Dashboard → Playback → Transcoding:

- **Intel iGPU/Arc → Intel QuickSync (QSV):** best option on Windows — no concurrent
  session cap, works headless. Update the Intel graphics driver from intel.com first.
- **NVIDIA GPU → NVENC:** works well; note consumer GeForce cards are capped at 3–5
  concurrent encode sessions on Windows (not patchable on Windows, unlike Linux). Fine
  for a home.
- Enable decode/encode for the codecs the GPU supports (H.264, HEVC; AV1 only on
  Arc/RTX 40+). Leave tone-mapping off unless HDR→SDR remote streams look washed out.
- No capable GPU → leave transcoding on CPU and rely on direct play; don't buy hardware
  until something actually transcodes (check Dashboard → Activity during playback).

## 4. Pi client: Jellyfin for Kodi vs JellyCon

The Pi still runs LibreELEC + Kodi (imaging/CEC/audio per
[libreelec-kodi.md](libreelec-kodi.md) — skip its SMB-source section). Two official
add-ons, both installed from the Jellyfin Kodi repository
(jellyfin.org/docs/general/clients/kodi/ — install the repo zip, then the add-on):

| | **Jellyfin for Kodi** (default choice) | **JellyCon** |
|---|---|---|
| Model | Syncs server library into Kodi's native DB | Browse-on-demand streaming add-on |
| Feel | Identical to local Kodi — fast native UI, works with skins/widgets | Add-on menu, queries server per screen |
| Multi-server/user switching | clunky | easy |
| Caveat | Owns the Kodi DB — don't mix with other scraped sources on the same Pi | Slightly slower navigation |

**Default: Jellyfin for Kodi** for a dedicated per-TV appliance (which this build is) —
native speed with server-side state. Install the **Kodi Sync Queue** plugin on the server
(Dashboard → Plugins → Catalog) so library changes push to clients promptly. Choose
JellyCon instead if the household needs per-person profile switching at the TV or runs
multiple servers.

Client config: add-on asks for the server address (`http://PC-IP:8096`) and a Jellyfin
user. Playback mode = **Native/direct paths off** (default "Addon" mode streams over
HTTP — simplest and avoids needing the SMB share on the Pi at all).

## 5. Direct play — why the PC stays idle

Jellyfin's playback ladder: **Direct Play** (client handles container+video+audio+subs →
file served as-is, zero transcode) → Direct Stream (remux only) → Transcode (CPU/GPU
work). A Pi 4/5 running Kodi direct-plays standard H.264/HEVC in MKV/MP4 with common
audio, so for a normal personal library the Windows PC just serves bytes — same load as
the plain SMB share. Transcoding appears only for: exotic codecs the Pi can't decode,
subtitle formats that force burn-in (PGS into some containers), or remote clients on
constrained bandwidth. If Dashboard → Activity shows constant transcoding for local
playback, fix the cause (usually subtitles or an AV1/VC-1 file on a non-decoding Pi)
rather than throwing hardware at it.

## 6. Users, sync, remote access

- Create one Jellyfin user per person (or per household profile). Each Pi's add-on signs
  in as a user; **resume points and watched state live on the server** — pause in the
  living room, resume in the bedroom, automatically.
- Remote/off-network access is free: simplest safe route is a VPN into the home network
  (UniFi's WireGuard/Teleport works well) or a reverse proxy with TLS. Do NOT port-forward
  8096 raw to the internet.

## 7. Updates

- Server: watch the stable channel (10.11.x point releases are safe). Major upgrades
  (→12.x): read the release notes first — 10.11 already migrated the DB to a single
  `jellyfin.db`, and majors can require add-on updates.
- Keep the Kodi add-on updated via the Jellyfin repo (it updates like any Kodi add-on);
  add-on and server majors should move together.
