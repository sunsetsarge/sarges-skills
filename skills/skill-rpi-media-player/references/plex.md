# Plex — Architecture C (the "only if already invested" option)

Verified 2026-07. Same shape as Jellyfin (server on the Windows PC, clients at each TV),
but closed-source/freemium with a worsening deal for self-hosters. Recommend it only when
the user already owns Plex Pass or is committed to the Plex ecosystem/apps.

## What changed (why Jellyfin is the default B)

- **April 2025:** free remote (off-network) streaming ended. Watching your own server away
  from home now requires **Remote Watch Pass** ($2.99/mo or $29.99/yr from June 2026) or
  full **Plex Pass**. LAN streaming of your own server is still free.
- **July 1, 2026:** lifetime Plex Pass price rose **$249.99 → $749.99** (existing lifetime
  holders grandfathered).
- Hardware transcoding still requires Plex Pass (Jellyfin: free).
- **The Pi client story is weak:** the standalone Plex Media Player app is discontinued/
  archived; the community Kodi add-ons (PlexKodiConnect, legacy PleXBMC) are effectively
  unmaintained — in contrast to Jellyfin's two officially maintained Kodi add-ons.

## If the user still wants Plex

- **Server:** Plex Media Server for Windows (plex.tv/media-server-downloads). Install,
  sign in, add libraries — same folder/naming conventions as Kodi/Jellyfin
  (`Title (Year)`, `Show/Season 01/Show S01E01`). Runs as a tray app by default; enable
  "start at login".
- **Pi client options, best-first:**
  1. **Plex HTMLTV app on a non-Pi device** — honestly, Plex's best TV clients are smart-TV
     /streaming-stick apps, not the Pi. If the user is Plex-committed, a cheap streaming
     stick per TV beats a Pi for Plex specifically. Say so.
  2. Pi running Kodi + **PlexKodiConnect** (github.com/troych/PlexKodiConnect) — works,
     syncs into the Kodi DB like Jellyfin-for-Kodi, but expect rough edges and slow
     maintenance; pin versions that work.
  3. Desktop Plex client under Raspberry Pi OS in kiosk mode — heavy, not recommended.
- **What still works free:** on-LAN playback of your own server to your own clients, which
  covers the this-skill use case. The paywall bites for remote access and HW transcoding.

## Migration note

Plex ↔ Jellyfin migration is folder-compatible (both scrape the same naming layout), so a
Plex user can trial Jellyfin side-by-side against the same media folders with zero risk —
suggest that to anyone chafing at the pricing. Watched-state migration needs third-party
tools; treat it as a fresh start unless the user pushes.
