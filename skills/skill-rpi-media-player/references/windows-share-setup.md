# Windows PC — Media Share Setup (SMB path, Architecture A)

The bundled `scripts/Set-MediaShare.ps1` does everything in this file in one idempotent
action. This reference exists so you can explain what it does, run pieces manually when
something is unusual, and handle the Windows-version quirks.

## Contents
1. [What the script does](#1-what-the-script-does)
2. [Running it](#2-running-it)
3. [Security model](#3-security-model)
4. [Windows 11 24H2 / Home vs Pro quirks](#4-windows-11-24h2--home-vs-pro-quirks)
5. [Stable addressing (DHCP reservation)](#5-stable-addressing-dhcp-reservation)
6. [Manual equivalents](#6-manual-equivalents)
7. [NFS instead of SMB?](#7-nfs-instead-of-smb)

## 1. What the script does

Given `-MediaPath` (the video folder), it:
1. Creates or reuses a **dedicated local account** (default `mediapi`) — password
   auto-generated and printed, never-expires, no interactive-logon profile needed.
2. Grants that account **NTFS read** on the media folder.
3. Creates (or corrects) the **SMB share** (default `Media`) with **Read** access for that
   account only — no Everyone, no guest.
4. Confirms **SMB1 is not enabled** (warns if the legacy feature is present) — SMBv2/v3
   only; Kodi doesn't support SMB1 and it must never be re-enabled as a "fix".
5. Enables the Windows firewall **File and Printer Sharing (SMB-In, TCP 445)** rule on the
   **Private profile only** — the share is never exposed on Public/domain-facing profiles.
6. Prints the connection block: `\\PC-NAME\Media`, `smb://pc-name/Media`, the IP variant,
   username, and password — ready to paste into Kodi.

Re-running is safe and is the standard repair step: it converges account, ACL, share,
and firewall back to this state and re-prints the connection info (existing passwords are
never changed unless `-ResetPassword` is passed).

## 2. Running it

From an **elevated** PowerShell prompt in the skill's `scripts\` folder:

```powershell
# Dry run — show what would change
.\Set-MediaShare.ps1 -MediaPath "D:\Videos" -WhatIf

# Real run with defaults (share 'Media', user 'mediapi')
.\Set-MediaShare.ps1 -MediaPath "D:\Videos"

# Custom names / forced new password
.\Set-MediaShare.ps1 -MediaPath "D:\Videos" -ShareName "Video" -ShareUser "kodi" -ResetPassword
```

It logs via `C:\Claude\Scripts\PowerShell\Logging_Functions.ps1` when present (Blaine's
standard logging library), otherwise to console + a local log file.

## 3. Security model

- **Never share with the user's own Windows credentials.** Kodi stores SMB credentials
  in plain text in its config (`passwords.xml`/sources); a dedicated read-only account
  means a stolen SD card leaks nothing that matters.
- **Read-only** at both NTFS and share level: a compromised or misbehaving Pi cannot
  modify/encrypt the library.
- **Private-profile-only firewall:** if the PC's network is categorized *Public*, sharing
  correctly fails — fix the network category (Settings → Network → the adapter →
  Private), don't open the Public profile.
- Password rotation: run with `-ResetPassword`, then update the source credentials in
  each Kodi (Settings → Media → the source → Edit).

## 4. Windows 11 24H2 / Home vs Pro quirks

- **Pro/Enterprise on 24H2+: SMB signing is required by default**, and signing is
  incompatible with guest credentials — so **guest/anonymous access from a Pi fails
  outright**, regardless of any "insecure guest logon" toggles. The dedicated-account
  approach sidesteps this entirely (Samba/Kodi negotiate signing fine with real
  credentials). If a share worked "with no password" before an upgrade and broke — this
  is why; the fix is the account, not registry surgery.
- **Home** doesn't enforce signing by default and lacks the Local Users and Groups MMC —
  but `New-LocalUser`/`net user` (what the script uses) work fine on Home.
- If the PC is signed in with a **Microsoft account**, that's irrelevant to the Pi — the
  dedicated *local* account is what Kodi authenticates with.
- "Network discovery" being off does NOT block direct `\\PC\Media` access — it only
  affects browsing. Type paths; don't chase discovery.

## 5. Stable addressing (DHCP reservation)

Kodi sources reference the server by name or IP; either must be stable:
- Best: **DHCP reservation for the PC** in the router (UniFi: Client → Settings → Fixed
  IP). Do the same for each Pi.
- Hostname (`\\PC-NAME\Media`) usually resolves via mDNS/NetBIOS on a flat home LAN, but
  across VLANs or with mDNS filtering it may not — in that case use the reserved IP in
  the Kodi source. (On a UniFi multi-VLAN network, also verify inter-VLAN firewall rules
  allow the Pi VLAN → PC TCP 445.)

## 6. Manual equivalents

What the script automates, for reference/debugging (elevated PowerShell):

```powershell
# Account
New-LocalUser -Name mediapi -Password (Read-Host -AsSecureString) -PasswordNeverExpires -AccountNeverExpires

# NTFS read
icacls "D:\Videos" /grant "mediapi:(OI)(CI)RX"

# Share (SMBv2/3 is automatic; SMB1 must simply not be installed)
New-SmbShare -Name Media -Path "D:\Videos" -ReadAccess mediapi

# Verify SMB1 is absent/disabled
Get-WindowsOptionalFeature -Online -FeatureName SMB1Protocol | Select State
Get-SmbServerConfiguration | Select EnableSMB1Protocol, EnableSMB2Protocol

# Firewall — Private only
Set-NetFirewallRule -Name 'FPS-SMB-In-TCP' -Enabled True -Profile Private

# Check who's connected later
Get-SmbSession; Get-SmbOpenFile
```

## 7. NFS instead of SMB?

Kodi supports NFS and it's marginally lighter-weight, but Windows is a poor NFS server
(Server editions only, or third-party). On a Windows source, **SMB is the right answer**;
consider NFS only if the library ever moves to a NAS/Linux box. DLNA is strictly worse
for this use case (no watched-state, poor seeking, flaky metadata) — don't use it except
for quick ad-hoc streaming to devices you don't control.
