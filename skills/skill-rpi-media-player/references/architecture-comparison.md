# Architecture Comparison — Pi Media Playback from a Windows PC

Verified 2026-07. Three viable shapes plus one advanced variant. Present the default (A),
state the tradeoff, and let the runtime answers (TV count, sync, remote access) decide.

## A — LibreELEC + Kodi per Pi, direct SMB to the Windows share (DEFAULT)

```
Windows PC ──SMB share (read-only)──▶ LAN ──▶ Pi/Kodi (TV 1)
                                          └─▶ Pi/Kodi (TV 2)
```

- **PC side:** nothing running — just an SMB share (`Set-MediaShare.ps1`). No service to
  babysit, no server to update, nothing breaks while the PC is busy doing other work.
- **Pi side:** LibreELEC boots straight into Kodi; Kodi mounts the share and keeps its own
  local library DB (metadata, artwork, watched flags).
- **Playback:** Pi pulls the raw file and decodes locally — the PC never transcodes.
- **Costs:** each Pi has an independent library. Watched/resume state does NOT sync between
  TVs. Library scans run per-Pi (new file appears on TV 2 only after TV 2 rescans — set
  "Update library on startup" or scheduled scans).
- **Best for:** 1–3 TVs, no sync requirement, "just play my files" reliability.

## B — Jellyfin Server on the Windows PC + Jellyfin add-on in Kodi on each Pi

```
Windows PC [Jellyfin Server 10.11.x] ──HTTP──▶ Pi/Kodi + Jellyfin-for-Kodi (TV 1..n)
```

- **PC side:** Jellyfin Server (free, open-source) indexes the library once, centrally.
- **Pi side:** still LibreELEC + Kodi, plus the Jellyfin add-on (see
  [jellyfin.md](jellyfin.md) for the *Jellyfin for Kodi* vs *JellyCon* choice).
- **Wins:** one library scanned once; **resume/watched state syncs across every TV**;
  per-person user profiles; free remote/off-network access; phone/tablet/browser clients.
- **Costs:** a Windows service that must be running to watch anything; server + add-on
  updates to keep roughly in step; slightly more moving parts.
- **Transcoding is the exception, not the rule:** Jellyfin direct-plays when the client
  handles container+codecs — a Pi 4/5 with Kodi direct-plays normal H.264/HEVC MKV/MP4,
  so the PC just serves bytes. Transcoding kicks in for exotic codecs, forced subtitle
  burn-in, or bandwidth-limited remote streams; enable QSV/NVENC hardware transcoding if
  the PC has it (details in jellyfin.md).
- **Best for:** many TVs, cross-TV sync, off-network viewing, multiple users.

## C — Plex (mention, don't push)

Same shape as B with Plex Media Server. Closed-source/freemium, and the economics moved
against self-hosters:

- **April 2025:** free remote (off-network) streaming ended — now requires Remote Watch
  Pass or Plex Pass. LAN streaming of your own server remains free.
- **July 2026:** lifetime Plex Pass jumped $249.99 → $749.99.
- **Pi client story is weak:** Plex Media Player is discontinued; the community Kodi
  add-ons (PlexKodiConnect etc.) are effectively unmaintained — vs Jellyfin's two
  officially maintained Kodi add-ons.

Recommend C only if the user already owns Plex Pass / is invested in the Plex ecosystem.
For everyone else, B (Jellyfin) is the same capability without the paywall risk.

## A+ — Kodi shared MySQL/MariaDB library ("sync without a server", advanced)

Kodi natively supports pointing every instance at one central MySQL/MariaDB database, so
watched/resume state and the library itself are shared across Pis with **no media server**:

- Run MariaDB on the Windows PC (or any always-on box). Kodi needs MySQL ≥5.7.9 or
  MariaDB ≥10.2.5.
- Each Pi gets an `advancedsettings.xml` with the same `<videodatabase>`/`<musicdatabase>`
  block pointing at the DB host.
- Media still streams over the plain SMB share; only metadata lives in the DB.
- **Hard constraint:** every Kodi instance must run the same major Kodi version — a
  Kodi upgrade migrates the shared DB and orphans older clients. With LibreELEC
  auto-updates this WILL eventually bite unless updates are managed deliberately.
- Verdict: works, documented on the Kodi wiki (kodi.wiki/view/MySQL), but for most users
  who want sync, Jellyfin (B) is less fragile for the same outcome. Offer A+ only to a
  user who explicitly doesn't want a media server and will manage versions.

## Decision procedure

1. Sync or remote access wanted → **B**.
2. Otherwise → **A**.
3. Already paying for Plex → **C** is acceptable; note the constraints above.
4. Wants sync but refuses a media server → **A+**, eyes open.

Migration comfort: A → B later is cheap (install Jellyfin, point it at the same folders,
add the add-on to each Pi). Starting with A loses nothing.
