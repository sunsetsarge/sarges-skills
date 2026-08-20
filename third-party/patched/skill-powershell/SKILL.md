---
name: skill-powershell
description: "PowerShell script creation with error prevention, logging, and reuse enforcement. Use this skill whenever the user mentions powershell, script, automate, .ps1, batch file, or asks to write any Windows automation script. Also trigger when debugging PowerShell errors, creating scheduled tasks via PS, or working with PowerShell modules. This skill enforces mandatory structure, syntax rules from past errors, and the Script Reuse mandate to prevent duplicate scripts."
---

# PowerShell Script Template Skill

**Confluence sources for auto-sync:**

| Source Page | Page ID | Content |
|-------------|---------|---------|
| PowerShell Script Template | 819201 | Template, syntax rules, checklists |
| Master Prompt Hub (APP-LL-017) | 786433 | Script Reuse mandate |
| Scripts Repository | 1015809 | Existing script inventory |

**Last synced:** 2026-04-17 | **Source versions:** Template v2.0, Hub v23.0

## Environment note
Paths like C:\... and D:\... are Blaine's Windows machine. In a remote/Cowork Linux session, reach them via the remote-device tools (device_bash / Desktop Commander), never the local Bash tool. Ports and paths were verified on the Windows box only. Any 'Last synced' tables are provenance only — do not attempt to sync; if a rule conflicts with observed reality, trust reality and flag for re-sync.

---

## Script Reuse Mandate (APP-LL-017) — DO THIS FIRST

Before writing ANY PowerShell script:

1. Audit `C:\Claude\Scripts\PowerShell\` by keyword via the scripts index or filename/content search — the folder has thousands of files; never a manual listing
2. Check Confluence Scripts Repository (page 1015809) for logged scripts
3. If a match exists: dot-source or adapt it — do not rewrite from scratch
4. Dot-source `Logging_Functions.ps1` (or `Write-Log.ps1`) for all logging
5. After completion: save to canonical path and log in Confluence Scripts Repository
6. Update local index if new script created
7. Follow Versioning Protocol if updating an existing script

---

## Pre-Creation Checklist

1. Fetch and review PowerShell Syntax Errors page (Confluence ID: 884737)
2. Check if similar script exists (Script Reuse above)
3. Confirm target path and naming convention with user
4. Identify logging requirements

---

## Mandatory Script Structure

```powershell
# ============================================
# Script Name: [Descriptive-Name].ps1
# Purpose: [One-line description]
# Created: [Date]
# Author: Claude AI (for Blaine)
# Version: 1.0
# ============================================

#Requires -Version 5.1

# --- LOGGING FUNCTION SOURCE ---
# If Write-Log.ps1 is missing, define a minimal Write-Log inline rather than skipping logging — logs are how past errors were diagnosed.
. "C:\Claude\Scripts\PowerShell\Write-Log.ps1"

# --- PARAMETERS ---
param(
    [Parameter(Mandatory=$false)]
    [string]$InputPath,

    [Parameter(Mandatory=$false)]
    [string]$OutputPath
)

# --- VARIABLES ---
$ErrorActionPreference = "Stop"
$ScriptName = $MyInvocation.MyCommand.Name
$LogPath = "C:\Claude\Error_Logs\PowerShell\$ScriptName-$(Get-Date -Format 'yyyyMMdd').log"

# --- MAIN EXECUTION ---
try {
    Write-Log -Message "Script started: $ScriptName" -Path $LogPath -Level Info

    # [MAIN LOGIC HERE]

    Write-Log -Message "Script completed successfully" -Path $LogPath -Level Info
}
catch {
    Write-Log -Message "ERROR: $($_.Exception.Message)" -Path $LogPath -Level Error
    Write-Log -Message "Line: $($_.InvocationInfo.ScriptLineNumber)" -Path $LogPath -Level Error
    throw
}
finally {
    # Cleanup if needed
}
```

---

## Syntax Rules (Error Prevention)

### Quoting Rules

| Context | Use | Example |
|---------|-----|---------|
| Static strings | Single quotes | `'C:\Claude\Scripts'` |
| Variable expansion | Double quotes | `"Processing $filename"` |
| Nested quotes | Escape or alternate | `"Say 'hello'"` or `'Say "hello"'` |
| Paths with spaces | Double quotes | `"C:\Program Files\App"` |

### Common Pitfalls

- **Wrong:** `Write-Host "Value: '$variable'"` → **Right:** `Write-Host "Value: $variable"`
- **Wrong:** Concatenating paths with `+` → **Right:** Use `Join-Path`
- **Wrong:** Assuming file exists → **Right:** Always `Test-Path` first
- **Wrong:** Silent failures → **Right:** Use `$ErrorActionPreference = "Stop"`

### Error Handling Pattern

```powershell
try {
    # Risky operation
}
catch [System.IO.FileNotFoundException] {
    Write-Log -Message "File not found: $filePath" -Path $LogPath -Level Warning
}
catch {
    Write-Log -Message "Unexpected error: $_" -Path $LogPath -Level Error
    throw
}
```

---

## Pre-Delivery Checklist

Before providing script to user:

1. Outputs/logs default under `C:\Claude\` (Blaine's one indexed workspace — scripts elsewhere get lost and rewritten); deviate only when the user names a path
2. Logging function is sourced
3. Try/catch wraps main logic
4. Variables use appropriate quote style
5. Comments explain non-obvious logic
6. Error messages are descriptive
7. Script tested mentally for edge cases
8. Version comment in header

## Post-Delivery Actions

After user confirms script works:

1. Save to `C:\Claude\Scripts\PowerShell\[name].ps1`
2. Add to Scripts Repository (Confluence page 1015809)
3. If errors during dev: update PowerShell Syntax Errors page (884737)
4. Log chat if substantial troubleshooting occurred

## Testing Commands

```powershell
# Syntax check (doesn't execute)
$script = Get-Content "C:\Claude\Scripts\PowerShell\ScriptName.ps1" -Raw
$null = [System.Management.Automation.PSParser]::Tokenize($script, [ref]$null)

# Dry run
.\ScriptName.ps1 -WhatIf

# Verbose execution
.\ScriptName.ps1 -Verbose
```
