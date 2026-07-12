# Variant D — Pi as Headless Plex SERVER, Apple TV / Infuse as Clients

Proven live on Blaine's "mediapi" build (2026-07-05 → 07-12). Use this variant when the TVs
already have good players (Apple TV, streaming sticks, smart TVs) — the Pi then serves files
instead of being the player. This **inverts** the skill's default (Kodi ON the Pi).

## Contents
1. [When to pick this over A/B/C](#1-when-to-pick-this-over-abc)
2. [The golden rule: the Pi must never transcode](#2-the-golden-rule-the-pi-must-never-transcode)
3. [Build steps](#3-build-steps)
4. [Home videos: the VFR/HEVC trap and the fix](#4-home-videos-the-vfrhevc-trap-and-the-fix)
5. [Keep-the-Pi-light settings](#5-keep-the-pi-light-settings)
6. [Monitoring & backups](#6-monitoring--backups)
7. [Parental controls (library separation)](#7-parental-controls-library-separation)
8. [Hard-won rules from the live build](#8-hard-won-rules-from-the-live-build)

## 1. When to pick this over A/B/C

- Household watches on **Apple TVs** (or Fire/Roku/smart TVs) → those devices decode video far
  better than any Pi; don't put a Pi behind each TV. One Pi 4 + USB drive = whole-house server.
- Best pairing: **Plex Media Server on the Pi** (library brain: metadata, watched/resume sync,
  profiles) + **Infuse on Apple TV as the player** (direct-plays everything, never asks the
  server to transcode). Keep the Plex app installed as backup/remote client.
- Jellyfin server on the Pi is the FOSS equivalent if the user objects to Plex accounts.

## 2. The golden rule: the Pi must never transcode

A Pi 4 has **no HEVC hardware encoder** (and weak CPU encode). Any client/server combination
that triggers server-side transcoding WILL fail: "not capable" errors, clips stopping after
seconds, or choppy playback while the transcode buffer seesaws. Design so everything
**direct-plays**: compatible files (H.264/HEVC the client decodes, CFR, AAC audio) + clients
set to Original/Maximum quality + Infuse as the player of choice. If the PC's fans or the Pi's
CPU spike during playback, something is transcoding — find the trigger, don't buy hardware.

## 3. Build steps

1. **Raspberry Pi OS (Lite is fine), wired Ethernet**, distinct hostname, SSH on
   (`sudo systemctl enable --now ssh`), key auth. Disable WiFi once wired
   (`dtoverlay=disable-wifi` in /boot/config.txt) — one interface, one IP, no ambiguity.
2. **USB drive as ext4** (NOT NTFS: ntfs-3g on a Pi caps writes ~30–40 MB/s CPU-bound vs
   ~100 MB/s ext4 — 3× slower network loading). Mount by UUID in /etc/fstab with **nofail**
   at /mnt/media. Media lives on the drive; the SD card stays disposable.
3. **Plex Media Server** (official plex.tv deb repo; armhf runs fine on 32-bit userland).
   Claim at `http://<pi>:32400/web`. If the user's Plex account was created via Apple's
   "Hide My Email" on the Apple TV, they MUST claim with **Continue with Apple** (same Apple
   ID) — email/Google sign-in silently creates a second account and the ATV sees no server.
4. **Samba share** of /mnt/media for loading files from the PC (dedicated user; map a drive
   letter + desktop shortcut on Windows). Note: mapped drives show "Unavailable" if the Pi
   was offline at Windows logon — `net use M: /delete` + re-map, or use the UNC path.
5. **DHCP reservation for the Ethernet MAC** (not the WiFi MAC) in the router, day one.
6. Library folders: `Movies`, `TV Shows`, `Music`, `Home Videos`, `_Inbox` (staging),
   `Restricted/...` (adult, separate libraries — see §7). Scraper naming conventions as in
   the main skill (`Title (Year)`, `Show/Season 01/Show S01E01`).
7. **Reboot acceptance test**: drive auto-mounts, Plex + Samba return unaided.

## 4. Home videos: the VFR/HEVC trap and the fix

**Trap:** phone footage (iPhone especially) is HEVC in .MOV with **variable frame rate**;
slo-mo clips are 120/240 fps. VFR (+ HEVC on clients that can't decode it) forces Plex to
transcode → the Pi fails (see §2). Regular movies direct-play fine, so this surfaces as
"movies fine, home videos broken."

**Fix (one-time, on a real PC — never the Pi):**
1. **Archive originals first** (byte-verify counts/sizes; they're irreplaceable). Keep them
   outside any Plex-scanned folder forever.
2. Batch re-encode to **CFR H.264 High + AAC + faststart**. NVENC (any modern NVIDIA GPU) is
   fine for playback copies since lossless originals are archived:
   `ffmpeg -i IN.MOV -map 0:v:0 -map "0:a:0?" -vf "fps=30000/1001" -c:v h264_nvenc -profile:v high -preset p5 -tune hq -rc vbr -cq 19 -b:v 0 -maxrate 25M -bufsize 50M -pix_fmt yuv420p -c:a aac -b:a 256k -movflags +faststart OUT_cfr.mp4`
   Archival-CPU alternative: `-c:v libx264 -preset slow -crf 16`.
3. **Match `fps=` to the source's nominal rate** (29.97 → `30000/1001`, 24 → `24000/1001`);
   **slo-mo (≥100 fps nominal) → `fps=60`** (smooth + preserves the slow-motion look);
   interlaced sources (old DV) → prepend `yadif,` to the filter.
4. Verify outputs (`ffprobe`: codec=h264, r_frame_rate == avg_frame_rate), swap them into the
   library, move originals out of the scanned folder, rescan. Acceptance = Plex shows
   **Direct Play** and the Pi's CPU stays idle during playback.
5. Plex "Optimize versions" is NOT the fix (it runs the same doomed transcode on the Pi);
   client "Original quality" helps but can't stop VFR-forced transcodes.

## 5. Keep-the-Pi-light settings

Set via Plex API (`PUT /:/prefs?Key=val&X-Plex-Token=...`; token is in Preferences.xml) or UI:
`GenerateBIFBehavior=never`, `GenerateChapterThumbBehavior=never`,
`GenerateIntroMarkerBehavior=never`, `GenerateCreditsMarkerBehavior=never`,
`LoudnessAnalysisBehavior=never`, `ButlerTaskDeepMediaAnalysis=0`.
Also: DLNA off, "networks allowed without auth" EMPTY (an entry there disables all user
restrictions), remote access only if wanted. Target: Plex idles ~2% CPU; `vcgencmd
get_throttled` stays 0x0 (sticky since boot — reboot to reset the baseline after changes).

## 6. Monitoring & backups

Two small scripts + cron (deployed pattern, adapt paths):
- `/usr/local/bin/mediapi-health.sh` (every 6 h): temp >75°C, throttle ≠0x0, disk ≥90%,
  `smartctl -H` (install smartmontools), services active → appends OK/ALERT lines to
  `/mnt/media/_health.log` (visible from the PC over the share), self-truncates to 500 lines.
- `/usr/local/bin/mediapi-backup.sh` (nightly): tar Plex `Plug-in Support/Databases` +
  `Preferences.xml` to `/mnt/media/_backups/plex/`, keep 7. The DB (watched state, metadata)
  is the only irreplaceable server state; backing it up to the data drive survives SD death.
- Test the alert path when deploying (run with `DISK_ALERT_PCT=1` and confirm the ALERT line).

## 7. Parental controls (library separation)

Rating filters depend on metadata and hide unrated items (= home videos vanish for kids).
The robust free design is **separation**: adult content in its own folders → own Plex
libraries → NOT shared to the managed Kids user. Kids' devices sign into the Kids profile
only; keep the SMB password off kids' devices; PIN the adult Plex profiles. NOTE: **Infuse
does not support Plex managed users** — on kid-facing TVs use the Plex app, or set Infuse's
own Allowed-Ratings PIN lock.

## 8. Hard-won rules from the live build

1. **Movies fine + home videos broken = transcode problem**, not a network problem. Check
   codec/frame-rate with ffprobe before touching the network.
2. **`throttled=0xe0000` on a "serving-only" Pi means something is making it work** — find
   the transcode/analysis job. The flag is sticky since boot; reboot for a clean baseline.
3. **ext4 over NTFS for a Pi media drive**, unless the drive must plug into Windows.
4. **Windows→Pi bootstrap**: fresh Pi OS has SSH off; headless password SSH hangs on the
   host-key prompt — use `plink -batch -hostkey <fp> -pw` once, then install a key. Pipe
   remote scripts as base64 (`echo <b64> | base64 -d | bash`); PowerShell pipes inject a BOM
   that breaks `bash -s`.
5. **robocopy exit codes 1–7 are SUCCESS** — don't treat as failure in automation.
6. **"Hide My Email" Plex accounts**: always claim/sign in with the same Apple ID everywhere;
   set a real password afterwards for non-Apple devices (Fire tablets).
7. Never re-encode, analyze, or Optimize on the Pi. The PC (or any x86 box) does heavy
   lifting; the Pi serves bytes.
