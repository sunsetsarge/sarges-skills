# Troubleshooting — by Symptom

Work top-down inside the matching symptom; each list is ordered by likelihood.

## Contents
1. [Kodi can't browse / can't find the PC](#1-kodi-cant-browse--cant-find-the-pc)
2. [Authentication fails](#2-authentication-fails)
3. [Playback stutters or buffers](#3-playback-stutters-or-buffers)
4. [TV remote doesn't control Kodi (CEC)](#4-tv-remote-doesnt-control-kodi-cec)
5. [Library scraped wrong / files missing](#5-library-scraped-wrong--files-missing)
6. [No sound / wrong sound](#6-no-sound--wrong-sound)
7. [Pi won't boot / SD corruption](#7-pi-wont-boot--sd-corruption)
8. [Jellyfin-specific](#8-jellyfin-specific)
9. [Useful commands](#9-useful-commands)

## 1. Kodi can't browse / can't find the PC

1. **Browsing being empty is normal** (NetBIOS discovery rarely works on modern networks).
   Type the path: Add network location → server `PC-NAME` or the reserved IP, share
   `Media`. Only debug further if a *typed* path fails.
2. Typed name fails but IP works → name resolution; use the IP (it's reserved) and move on.
3. IP fails too:
   - PC awake? Check Windows fast-startup/sleep — set the PC to not sleep while serving,
     or enable Wake-on-LAN.
   - `Test-NetConnection -ComputerName <pi-ip>` from the PC (pings the Pi) and from the Pi
     `ssh root@kodi-xxx` then `nc -zv <pc-ip> 445`. If 445 is blocked: firewall rule not
     enabled for the active profile, or the PC's network is categorized *Public* — re-run
     `Set-MediaShare.ps1` and check the network category.
   - VLANs (UniFi): confirm the Pi's VLAN can reach the PC's VLAN on TCP 445.
4. Kodi SMB settings: Settings → Services → SMB client → min **SMBv2** / max **SMBv3**.
   Never enable SMB1 anywhere.

## 2. Authentication fails

1. Re-check the exact username/password from the script output (`mediapi` + generated
   password). Kodi caches bad credentials: remove the source, also check
   `/storage/.kodi/userdata/passwords.xml` via SSH and delete stale entries, restart Kodi.
2. Guest/no-credentials access on Windows 11 Pro 24H2+ **cannot work** (SMB signing ×
   guest are mutually exclusive). Use the account; don't fight it.
3. Account locked/expired? `net user mediapi` on the PC — the script sets never-expire,
   but domain policies can override. Re-run the script; `-ResetPassword` if needed.
4. "Use legacy security" in Kodi's SMB settings is a last resort for odd NTLM issues —
   toggle, restart Kodi, retest; turn it back off if it didn't help.

## 3. Playback stutters or buffers

Decide first: **network problem or decode problem?**
- Same file stutters at the same timestamps every play → decode. Stutter varies with time
  of day / other traffic → network.

Decode:
1. Check what the file actually is:
   `ffprobe -v error -select_streams v:0 -show_entries stream=codec_name,width,height,bit_rate <file>`
2. **H.264 4K/high-bitrate on a Pi 5** → expected (no H.264 hardware decode). Play it on a
   Pi 4, or re-encode to HEVC, or accept 1080p versions.
3. AV1/VC-1 → neither Pi decodes these in hardware; 1080p AV1 is OK on Pi 5 in software.
4. Thermal: `vcgencmd measure_temp` via SSH during playback; >80°C throttles — add the
   heatsink/fan case, don't wedge the Pi in a zero-airflow pocket behind the TV.

Network:
1. Wi-Fi + 4K/high-bitrate = the answer. Wire it, or lower the bitrate.
2. Wired but stuttering: check negotiated link speed (`ethtool eth0` via SSH — should be
   1000Mb/s; 100Mb/s means a bad cable), and test raw throughput with `iperf3` (server on
   PC, client on Pi).
3. PC disk busy (backups, OneDrive sync storms) can starve reads — check Task Manager
   during a stutter.

## 4. TV remote doesn't control Kodi (CEC)

1. CEC enabled **on the TV**? Each brand names it differently (Anynet+/Bravia Sync/
   SimpLink/Viera Link/EasyLink). It's often off by default.
2. **Pi 5: TV must be on the HDMI port nearest the USB-C power connector.** Move the plug.
3. Reboot order matters for detection: TV on first, then power the Pi.
4. The HDMI cable must pass the CEC pin — nearly all do, but promiscuous switches/
   soundbars in the chain can eat CEC; test with a direct TV connection.
5. Kodi: Settings → System → Input → Peripherals → CEC Adapter — present and enabled?
   (Duplicate adapter entries on Pi 5 are cosmetic.)
6. Still dead → the TV's CEC is just bad (some are): Kore app, air-mouse, or Flirc IR as
   fallbacks.

## 5. Library scraped wrong / files missing

1. Wrong movie/show matched → filename doesn't carry `(Year)` / `SxxEyy`. Fix names, then
   library → "Refresh" on the item (choose the right match manually if offered).
2. Files not appearing → source content-type set? File extension supported? Scan the
   specific source (Videos → Files → source → context menu → Scan for new content).
3. Mass mess (renamed everything after a bad scan) → cleanest reset: Settings → Media →
   Library → Clean library, then rescan; worst case delete the video DB via SSH
   (`/storage/.kodi/userdata/Database/MyVideos*.db`) and rescan fresh.
4. Under Jellyfin-for-Kodi: fix on the **server** (identify/refresh there), then let Kodi
   sync; never mix another scraped SMB source into the same Kodi's DB.

## 6. No sound / wrong sound

1. Menu clicks but silent dialogue → passthrough sending a codec the TV/AVR can't decode:
   disable the unsupported codecs in Settings → System → Audio, or turn passthrough off.
2. No audio at all → audio output device should be the HDMI/PI device (not analogue);
   check TV input's audio format setting (some TVs need "PCM" from the TV side menu).
3. Lip-sync drift → audio-offset dial in the video OSD; if consistent everywhere, set a
   global offset.

## 7. Pi won't boot / SD corruption

1. Rainbow screen / no HDMI → power first: use the official PSU (Pi 4 5V/3A, Pi 5 5V/5A);
   lightning-bolt icon = undervoltage = the (usually third-party) PSU is the fault.
2. Boot loops or filesystem errors → reflash from the **golden image** (15 minutes, loses
   nothing — media is on the PC; only per-Pi tweak to redo is the hostname).
3. Recurring corruption on one unit → the SD card is dying; replace with a quality A2 card
   and reflash. Chronic across units → power or unsafe shutdowns (add "power off" to the
   user's routine instead of yanking the plug, though LibreELEC's read-only FS tolerates a
   lot).

## 8. Jellyfin-specific

1. Client can't reach server → `http://PC-IP:8096` in a browser from another device; if
   dead: service running? (`Get-Service Jellyfin*`) firewall 8096 on Private profile?
2. Everything transcodes (PC fans roar) → Dashboard → Activity shows the reason per
   stream; usual culprits are subtitle burn-in (switch subtitle format/setting) or a
   client bitrate cap left at a low default (raise it in the client's playback settings).
3. Add-on stopped syncing after a server upgrade → update the Kodi add-on / repo; check
   Kodi Sync Queue plugin version matches the server major.
4. New files not appearing → real-time monitoring only watches local disks reliably; run/
   schedule a library scan.

## 9. Useful commands

```bash
# On the Pi (ssh root@kodi-xxx, password set at first boot)
vcgencmd measure_temp                 # SoC temperature
vcgencmd get_throttled                # 0x0 = never throttled/undervolted
journalctl -b | grep -i cec           # CEC detection at boot
cat /storage/.kodi/temp/kodi.log      # Kodi log (grep -i 'smb\|error')
```

```powershell
# On the PC
Get-SmbSession                        # which Pis are connected
Get-SmbOpenFile                       # what they're reading
Get-SmbServerConfiguration | Select EnableSMB1Protocol,EnableSMB2Protocol
Test-NetConnection <pi-ip> -Port 22   # reach a Pi's SSH
```
