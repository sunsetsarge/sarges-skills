# ============================================
# Script Name: Set-MediaShare.ps1
# Purpose: One-action, idempotent setup of a secure read-only SMB media share
#          for Raspberry Pi / Kodi clients (skill-rpi-media-player).
# Created: 2026-07-04
# Author: Claude AI (for Blaine)
# Version: 1.0
# ============================================
# Creates/repairs: dedicated read-only local account, NTFS read ACL, SMBv2/v3
# share, Private-profile-only firewall rule. Prints the exact paths and
# credentials to paste into Kodi. Safe to re-run any time (convergent).
#
#   .\Set-MediaShare.ps1 -MediaPath "D:\Videos" -WhatIf     # dry run
#   .\Set-MediaShare.ps1 -MediaPath "D:\Videos"             # defaults: Media / mediapi
#   .\Set-MediaShare.ps1 -MediaPath "D:\Videos" -ShareName Video -ShareUser kodi -ResetPassword

#Requires -Version 5.1
#Requires -RunAsAdministrator

[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [Parameter(Mandatory = $true)]
    [string]$MediaPath,

    [Parameter(Mandatory = $false)]
    [ValidatePattern('^[A-Za-z0-9_\-]{1,64}$')]
    [string]$ShareName = 'Media',

    [Parameter(Mandatory = $false)]
    [ValidatePattern('^[A-Za-z0-9_\-]{1,20}$')]
    [string]$ShareUser = 'mediapi',

    # Force a new password even if the account already exists.
    [switch]$ResetPassword
)

$ErrorActionPreference = 'Stop'
$ScriptName = 'Set-MediaShare'

# --- LOGGING ---------------------------------------------------------------
# Use Blaine's shared logging library when present; otherwise self-contained
# fallback so the packaged skill works on any Windows machine.
$LoggingLib = 'C:\Claude\Scripts\PowerShell\Logging_Functions.ps1'
if (Test-Path $LoggingLib) {
    . $LoggingLib
    Start-ClaudeScript -ScriptName $ScriptName
} else {
    $Global:CurrentLogFile = Join-Path $env:TEMP ("{0}_{1}.log" -f $ScriptName, (Get-Date -Format 'yyyy-MM-dd_HHmmss'))
    function Write-ClaudeLog {
        param(
            [Parameter(Mandatory)][string]$Message,
            [ValidateSet('INFO','WARNING','ERROR','SUCCESS','DEBUG')][string]$Level = 'INFO'
        )
        $entry = "[{0}] [{1}] {2}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Level, $Message
        Add-Content -Path $Global:CurrentLogFile -Value $entry -Encoding UTF8
        $colors = @{ INFO = 'White'; WARNING = 'Yellow'; ERROR = 'Red'; SUCCESS = 'Green'; DEBUG = 'Gray' }
        Write-Host $entry -ForegroundColor $colors[$Level]
    }
    Write-ClaudeLog -Message "START $ScriptName -- log: $Global:CurrentLogFile"
}

function New-RandomPassword {
    # 20 chars from an unambiguous set (no l/1/I/O/0, no shell-hostile chars)
    # -- it gets typed into a Kodi on-screen keyboard.
    $chars = 'abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789'.ToCharArray()
    $bytes = New-Object byte[] 20
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    -join ($bytes | ForEach-Object { $chars[ $_ % $chars.Count ] })
}

$GeneratedPassword = $null

try {
    # --- 0. Validate input ---------------------------------------------------
    if (-not (Test-Path -Path $MediaPath -PathType Container)) {
        throw "MediaPath does not exist or is not a folder: $MediaPath"
    }
    $MediaPath = (Resolve-Path $MediaPath).Path
    Write-ClaudeLog -Message "Target media folder: $MediaPath (share '$ShareName', user '$ShareUser')"

    # --- 1. Dedicated read-only local account --------------------------------
    $existingUser = Get-LocalUser -Name $ShareUser -ErrorAction SilentlyContinue
    if (-not $existingUser) {
        if ($PSCmdlet.ShouldProcess("local user '$ShareUser'", 'Create')) {
            $GeneratedPassword = New-RandomPassword
            $secure = ConvertTo-SecureString $GeneratedPassword -AsPlainText -Force
            New-LocalUser -Name $ShareUser -Password $secure `
                -Description "Read-only media share account (skill-rpi-media-player)" `
                -PasswordNeverExpires -AccountNeverExpires -UserMayNotChangePassword | Out-Null
            Write-ClaudeLog -Message "Created local user '$ShareUser' (password never expires)" -Level SUCCESS
        }
    } else {
        Write-ClaudeLog -Message "Local user '$ShareUser' already exists"
        if (-not $existingUser.Enabled) {
            if ($PSCmdlet.ShouldProcess("local user '$ShareUser'", 'Enable')) {
                Enable-LocalUser -Name $ShareUser
                Write-ClaudeLog -Message "Re-enabled disabled account '$ShareUser'" -Level WARNING
            }
        }
        if ($ResetPassword) {
            if ($PSCmdlet.ShouldProcess("local user '$ShareUser'", 'Reset password')) {
                $GeneratedPassword = New-RandomPassword
                $secure = ConvertTo-SecureString $GeneratedPassword -AsPlainText -Force
                Set-LocalUser -Name $ShareUser -Password $secure
                Write-ClaudeLog -Message "Password reset for '$ShareUser' -- update credentials in every Kodi" -Level WARNING
            }
        }
    }
    # Keep the account out of Remote Desktop / interactive noise: it should be
    # a member of Users only (New-LocalUser adds no groups; nothing to strip).

    # --- 2. NTFS read access --------------------------------------------------
    $acl = Get-Acl -Path $MediaPath
    $hasRead = $acl.Access | Where-Object {
        $_.IdentityReference -like "*\$ShareUser" -and
        $_.AccessControlType -eq 'Allow' -and
        (($_.FileSystemRights -band [System.Security.AccessControl.FileSystemRights]::ReadAndExecute) -eq [System.Security.AccessControl.FileSystemRights]::ReadAndExecute)
    }
    if (-not $hasRead) {
        if ($PSCmdlet.ShouldProcess($MediaPath, "Grant NTFS ReadAndExecute to '$ShareUser'")) {
            $rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
                "$env:COMPUTERNAME\$ShareUser",
                [System.Security.AccessControl.FileSystemRights]::ReadAndExecute,
                @([System.Security.AccessControl.InheritanceFlags]::ContainerInherit, [System.Security.AccessControl.InheritanceFlags]::ObjectInherit),
                [System.Security.AccessControl.PropagationFlags]::None,
                [System.Security.AccessControl.AccessControlType]::Allow)
            $acl.AddAccessRule($rule)
            Set-Acl -Path $MediaPath -AclObject $acl
            Write-ClaudeLog -Message "Granted NTFS ReadAndExecute on $MediaPath to '$ShareUser'" -Level SUCCESS
        }
    } else {
        Write-ClaudeLog -Message "NTFS read access already in place"
    }

    # --- 3. SMB share (read-only, SMBv2/v3) ------------------------------------
    $share = Get-SmbShare -Name $ShareName -ErrorAction SilentlyContinue
    if ($share -and $share.Path -ne $MediaPath) {
        # Existing share points elsewhere -- never silently repoint someone's share.
        throw "Share '$ShareName' already exists but points at '$($share.Path)', not '$MediaPath'. Use a different -ShareName or remove the old share deliberately (Remove-SmbShare -Name $ShareName)."
    }
    if (-not $share) {
        if ($PSCmdlet.ShouldProcess("SMB share '$ShareName' -> $MediaPath", 'Create')) {
            New-SmbShare -Name $ShareName -Path $MediaPath -ReadAccess "$env:COMPUTERNAME\$ShareUser" `
                -Description 'Read-only media library for Pi/Kodi clients' | Out-Null
            Write-ClaudeLog -Message "Created share '$ShareName' with Read access for '$ShareUser'" -Level SUCCESS
        }
    } else {
        Write-ClaudeLog -Message "Share '$ShareName' already exists at correct path"
        # Converge permissions: ensure our user has Read; drop Everyone if present.
        $access = Get-SmbShareAccess -Name $ShareName
        if (-not ($access | Where-Object { $_.AccountName -like "*\$ShareUser" -and $_.AccessRight -in @('Read','Change','Full') })) {
            if ($PSCmdlet.ShouldProcess("share '$ShareName'", "Grant Read to '$ShareUser'")) {
                Grant-SmbShareAccess -Name $ShareName -AccountName "$env:COMPUTERNAME\$ShareUser" -AccessRight Read -Force | Out-Null
                Write-ClaudeLog -Message "Granted share Read to '$ShareUser'" -Level SUCCESS
            }
        }
        if ($access | Where-Object { $_.AccountName -eq 'Everyone' }) {
            if ($PSCmdlet.ShouldProcess("share '$ShareName'", "Revoke 'Everyone'")) {
                Revoke-SmbShareAccess -Name $ShareName -AccountName 'Everyone' -Force | Out-Null
                Write-ClaudeLog -Message "Revoked 'Everyone' from share (read-only dedicated account model)" -Level WARNING
            }
        }
    }

    # --- 4. SMB protocol sanity (never SMB1) -----------------------------------
    $smbCfg = Get-SmbServerConfiguration
    if ($smbCfg.EnableSMB1Protocol) {
        Write-ClaudeLog -Message 'SMB1 is ENABLED on this machine. Kodi does not use it and it is insecure -- disable with: Set-SmbServerConfiguration -EnableSMB1Protocol $false (and remove the SMB1Protocol Windows feature).' -Level WARNING
    } else {
        Write-ClaudeLog -Message 'SMB1 disabled (good); serving SMBv2/v3 only'
    }
    if (-not $smbCfg.EnableSMB2Protocol) {
        throw 'SMBv2/v3 is disabled on this machine (EnableSMB2Protocol = false). Enable it: Set-SmbServerConfiguration -EnableSMB2Protocol $true'
    }

    # --- 5. Firewall: SMB-In on Private profile only ---------------------------
    $fwRules = Get-NetFirewallRule -Name 'FPS-SMB-In-TCP', 'FPS-SMB-In-TCP-NoScope' -ErrorAction SilentlyContinue
    if (-not $fwRules) {
        # Localized/older systems may lack the canonical names; fall back to the group.
        $fwRules = Get-NetFirewallRule -DisplayGroup 'File and Printer Sharing' -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -like '*SMB-In*' }
    }
    if ($fwRules) {
        foreach ($r in $fwRules) {
            if ($PSCmdlet.ShouldProcess("firewall rule '$($r.Name)'", 'Enable for Private profile')) {
                Set-NetFirewallRule -Name $r.Name -Enabled True -Profile Private
            }
        }
        Write-ClaudeLog -Message "Enabled $($fwRules.Count) SMB-In firewall rule(s) on Private profile only" -Level SUCCESS
    } else {
        if ($PSCmdlet.ShouldProcess('firewall', "Create custom SMB-In rule (TCP 445, Private)")) {
            New-NetFirewallRule -DisplayName 'Media Share SMB-In (skill-rpi-media-player)' `
                -Direction Inbound -Protocol TCP -LocalPort 445 -Profile Private -Action Allow | Out-Null
            Write-ClaudeLog -Message 'Created custom SMB-In rule (TCP 445, Private profile)' -Level SUCCESS
        }
    }

    # Warn if the active network is Public -- the rule above will (correctly) not apply.
    $publicNets = Get-NetConnectionProfile | Where-Object { $_.NetworkCategory -eq 'Public' }
    if ($publicNets) {
        Write-ClaudeLog -Message ("Network '{0}' is categorized PUBLIC -- the share will not be reachable. Set it to Private: Set-NetConnectionProfile -InterfaceIndex {1} -NetworkCategory Private" -f $publicNets[0].Name, $publicNets[0].InterfaceIndex) -Level WARNING
    }

    # --- 6. Connection info -----------------------------------------------------
    $pcName = $env:COMPUTERNAME
    $ip = (Get-NetIPAddress -AddressFamily IPv4 -PrefixOrigin Dhcp, Manual -ErrorAction SilentlyContinue |
        Where-Object { $_.IPAddress -notlike '169.254.*' -and $_.IPAddress -ne '127.0.0.1' } |
        Select-Object -First 1).IPAddress
    if (-not $ip) { $ip = '<PC-IP>' }

    $passwordLine = if ($GeneratedPassword) {
        "Password    : $GeneratedPassword   <-- SAVE THIS; it is not stored anywhere"
    } else {
        'Password    : (unchanged -- use the existing one, or re-run with -ResetPassword)'
    }

    Write-Host ''
    Write-Host '================= PASTE INTO KODI =================' -ForegroundColor Cyan
    Write-Host "Windows path: \\$pcName\$ShareName"
    Write-Host "Kodi path   : smb://$pcName/$ShareName"
    Write-Host "IP variant  : smb://$ip/$ShareName   (use if the name does not resolve)"
    Write-Host "Username    : $ShareUser"
    Write-Host $passwordLine
    Write-Host '===================================================' -ForegroundColor Cyan
    Write-Host 'Reminder: give this PC a DHCP reservation in the router so the path stays stable.' -ForegroundColor Yellow

    Write-ClaudeLog -Message 'Script completed successfully' -Level SUCCESS
}
catch {
    Write-ClaudeLog -Message "ERROR: $($_.Exception.Message)" -Level ERROR
    Write-ClaudeLog -Message "Line: $($_.InvocationInfo.ScriptLineNumber)" -Level ERROR
    throw
}
