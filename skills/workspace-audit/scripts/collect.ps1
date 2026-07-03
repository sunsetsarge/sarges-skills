<#
  collect.ps1 -- workspace-audit fact collector (Checks 1-7; Check 8/Confluence is NOT here)

  GUARANTEES:
    - READ-ONLY. No Set-*, New-Item, Remove-*, Copy-*, Move-*, Rename-*, or any state
      mutation other than writing the single -OutFile the caller asked for.
    - NO NETWORK. No Invoke-WebRequest/Invoke-RestMethod calls of any kind.
      `git status`/`git status -sb` are local read-only repo queries and are allowed.
    - SECRET REDACTION. When reading settings.json, settings.local.json, ~\.claude.json,
      or claude_desktop_config.json: any property whose NAME matches
      (?i)token|key|secret|password|webhook|authorization is emitted as $true
      (presence only) -- the value is NEVER included. "env" blocks under mcpServers
      entries are emitted as key-name lists only; values are never included.
    - PowerShell 5.1 compatible: no &&, no ?: or ??, no -AsHashtable.
    - Always emits one valid JSON object, even when individual sections error out.

  Usage: powershell -NoProfile -ExecutionPolicy Bypass -File collect.ps1 [-OutFile <path>]
#>

param([string]$OutFile)

$ErrorActionPreference = 'Stop'
$ScriptVersion = '1.0.0'

# --- Paths (variables, per spec) -------------------------------------------
$ProjectsRoot      = 'C:\Users\blain\OneDrive\Documents\Claude\Projects'
$ClaudeMdPath      = Join-Path $ProjectsRoot 'CLAUDE.md'
$MemoryDir         = 'C:\Users\blain\.claude\projects\C--Users-blain-OneDrive-Documents-Claude-Projects\memory'
$MemoryMdPath      = Join-Path $MemoryDir 'MEMORY.md'
$WorkspaceOptDir   = Join-Path $ProjectsRoot 'Workspace Optimization'
$BaselinePath      = 'C:\Users\blain\.claude\audit\baseline.json'
$SettingsPath      = 'C:\Users\blain\.claude\settings.json'
$SettingsLocalPath = 'C:\Users\blain\.claude\settings.local.json'
$ClaudeJsonPath    = 'C:\Users\blain\.claude.json'
$DesktopCfgPath    = Join-Path $env:APPDATA 'Claude\claude_desktop_config.json'
$DesktopLogsDir    = Join-Path $env:APPDATA 'Claude\logs'
$CliNodeJsDir      = Join-Path $env:LOCALAPPDATA 'claude-cli-nodejs'
$SkillsDir         = 'C:\Users\blain\.claude\skills'
$RepoSkillsDir     = 'C:\Claude\sarges-skills\skills'
$RepoRoot          = 'C:\Claude\sarges-skills'
$ScriptsRoot       = 'C:\Claude\Scripts'
$ScriptsIndexPath  = Join-Path $ScriptsRoot 'SCRIPTS_INDEX.md'
$SecretNamePattern = '(?i)token|key|secret|password|webhook|authorization'
$ErrPattern        = '(?i)error|exception|failed'
$LogCutoff         = (Get-Date).AddDays(-14)

# --- Helpers -----------------------------------------------------------
function Redact-Object {
    # secret-named keys -> $true (presence only); "env" blocks -> key names only
    param($obj)
    $result = [ordered]@{}
    if ($null -eq $obj) { return $result }
    foreach ($prop in $obj.PSObject.Properties) {
        if ($prop.Name -match $SecretNamePattern) {
            $result[$prop.Name] = $true
        } elseif ($prop.Name -eq 'env') {
            $names = @()
            if ($prop.Value) { foreach ($ep in $prop.Value.PSObject.Properties) { $names += $ep.Name } }
            $result[$prop.Name] = @{ key_names = $names }
        } else {
            $result[$prop.Name] = $prop.Value
        }
    }
    return $result
}

function Get-FileFact {
    param([string]$Path)
    if (Test-Path -LiteralPath $Path -PathType Leaf) {
        $fi = Get-Item -LiteralPath $Path
        return [ordered]@{ path = $Path; exists = $true; size = $fi.Length; last_write = $fi.LastWriteTime.ToString('o') }
    }
    return [ordered]@{ path = $Path; exists = $false }
}

function Get-LogFact {
    # one log file -> path/size/last_write + error count (last 14d only) or a skip flag
    param([System.IO.FileInfo]$File)
    $entry = [ordered]@{ path = $File.FullName; size = $File.Length; last_write = $File.LastWriteTime.ToString('o') }
    if ($File.Length -gt 10MB) {
        $entry['skipped_large'] = $true
    } elseif ($File.LastWriteTime -ge $LogCutoff) {
        try {
            $entry['error_line_count_last_14d'] = (Select-String -LiteralPath $File.FullName -Pattern $ErrPattern -ErrorAction SilentlyContinue | Measure-Object).Count
        } catch {
            $entry['scan_error'] = $_.Exception.Message
        }
    } else {
        $entry['skipped_older_than_14d'] = $true
    }
    return $entry
}

$facts = [ordered]@{}

# --- meta --------------------------------------------------------------
try {
    $facts['meta'] = [ordered]@{ timestamp = (Get-Date).ToString('o'); hostname = $env:COMPUTERNAME; script_version = $ScriptVersion }
} catch { $facts['meta'] = [ordered]@{ error = $_.Exception.Message } }

# --- canary (Check 1) ----------------------------------------------------
try {
    $canary = [ordered]@{}
    $canary['claude_md'] = Get-FileFact $ClaudeMdPath
    $canary['memory_md'] = Get-FileFact $MemoryMdPath

    $woFiles = @()
    if (Test-Path -LiteralPath $WorkspaceOptDir) {
        Get-ChildItem -LiteralPath $WorkspaceOptDir -Filter '*.md' -Recurse -File -ErrorAction SilentlyContinue |
            ForEach-Object { $woFiles += (Get-FileFact $_.FullName) }
    }
    $canary['workspace_optimization_md_files'] = $woFiles

    $planSpecFiles = @()
    if (Test-Path -LiteralPath $ProjectsRoot) {
        foreach ($d1 in (Get-ChildItem -LiteralPath $ProjectsRoot -Directory -ErrorAction SilentlyContinue)) {
            Get-ChildItem -LiteralPath $d1.FullName -File -ErrorAction SilentlyContinue |
                Where-Object { $_.Name -match '^(PLAN|SPEC|SHIP_SPEC)\.md$' } |
                ForEach-Object { $planSpecFiles += (Get-FileFact $_.FullName) }
            foreach ($d2 in (Get-ChildItem -LiteralPath $d1.FullName -Directory -ErrorAction SilentlyContinue)) {
                Get-ChildItem -LiteralPath $d2.FullName -File -ErrorAction SilentlyContinue |
                    Where-Object { $_.Name -match '^(PLAN|SPEC|SHIP_SPEC)\.md$' } |
                    ForEach-Object { $planSpecFiles += (Get-FileFact $_.FullName) }
            }
        }
    }
    $canary['plan_spec_files'] = $planSpecFiles

    if (Test-Path -LiteralPath $BaselinePath) {
        $canary['baseline_found'] = $true
        try {
            $baseline = Get-Content -LiteralPath $BaselinePath -Raw | ConvertFrom-Json
            $baseCanonical = @()
            if ($baseline.canonical_files) { foreach ($p in $baseline.canonical_files) { $baseCanonical += (Get-FileFact $p) } }
            $canary['baseline_canonical_files'] = $baseCanonical
        } catch { $canary['baseline_read_error'] = $_.Exception.Message }
    } else {
        $canary['baseline_found'] = $false
    }
    $facts['canary'] = $canary
} catch { $facts['canary'] = [ordered]@{ error = $_.Exception.Message } }

# --- claude_md (Check 2a) -------------------------------------------------
try {
    if (Test-Path -LiteralPath $ClaudeMdPath) {
        $lines = Get-Content -LiteralPath $ClaudeMdPath
        $content = $lines -join "`n"
        $facts['claude_md'] = [ordered]@{
            exists = $true; line_count = $lines.Count
            has_directory_map       = [bool]($content -match 'Directory map')
            has_hard_rules          = [bool]($content -match 'Hard rules')
            has_model_cost_strategy = [bool]($content -match 'Model & cost strategy')
        }
    } else {
        $facts['claude_md'] = [ordered]@{ exists = $false }
    }
} catch { $facts['claude_md'] = [ordered]@{ error = $_.Exception.Message } }

# --- settings (Check 2b/2c) -----------------------------------------------
try {
    $settings = [ordered]@{}
    if (Test-Path -LiteralPath $SettingsPath) {
        $s = Get-Content -LiteralPath $SettingsPath -Raw | ConvertFrom-Json
        $hasHooks = $false
        foreach ($p in $s.PSObject.Properties) { if ($p.Name -eq 'hooks') { $hasHooks = $true } }
        $settings['settings_json_exists'] = $true
        $settings['has_hooks'] = $hasHooks
    } else { $settings['settings_json_exists'] = $false }

    if (Test-Path -LiteralPath $SettingsLocalPath) {
        $sl = Get-Content -LiteralPath $SettingsLocalPath -Raw | ConvertFrom-Json
        $settings['settings_local_exists'] = $true
        $settings['settings_local_top_level_keys'] = @((Redact-Object $sl).Keys)
    } else { $settings['settings_local_exists'] = $false }
    $facts['settings'] = $settings
} catch { $facts['settings'] = [ordered]@{ error = $_.Exception.Message } }

# --- skills (Check 3) ------------------------------------------------------
try {
    $skills = [ordered]@{}
    $installed = @()
    if (Test-Path -LiteralPath $SkillsDir) {
        Get-ChildItem -LiteralPath $SkillsDir -ErrorAction SilentlyContinue | ForEach-Object {
            $target = $null
            if ($_.LinkType -eq 'Junction' -and $_.Target) { $target = $_.Target | Select-Object -First 1 }
            $installed += [ordered]@{ name = $_.Name; link_type = $_.LinkType; target = $target }
        }
    }
    $skills['installed'] = $installed

    $repoSkillDirs = @()
    if (Test-Path -LiteralPath $RepoSkillsDir) {
        Get-ChildItem -LiteralPath $RepoSkillsDir -Directory -ErrorAction SilentlyContinue | ForEach-Object { $repoSkillDirs += $_.Name }
    }
    $skills['repo_skill_dirs'] = $repoSkillDirs

    $gitInfo = [ordered]@{}
    if (Test-Path -LiteralPath $RepoRoot) {
        try {
            Push-Location -LiteralPath $RepoRoot
            $sb = @(git status -sb 2>$null)
            Pop-Location
            if ($sb -and $sb.Count -gt 0) {
                $gitInfo['branch_line'] = $sb[0]
                $gitInfo['porcelain_line_count'] = @($sb | Select-Object -Skip 1).Count
                $ahead = 0; $behind = 0
                if ($sb[0] -match '\[ahead (\d+)') { $ahead = [int]$matches[1] }
                if ($sb[0] -match 'behind (\d+)') { $behind = [int]$matches[1] }
                $gitInfo['ahead'] = $ahead
                $gitInfo['behind'] = $behind
            } else { $gitInfo['error'] = 'no output from git status -sb' }
        } catch { $gitInfo['error'] = $_.Exception.Message }
    } else { $gitInfo['error'] = 'repo root not found' }
    $skills['repo_git_status'] = $gitInfo
    $facts['skills'] = $skills
} catch { $facts['skills'] = [ordered]@{ error = $_.Exception.Message } }

# --- mcp (Check 4) -----------------------------------------------------------
try {
    $mcp = [ordered]@{}

    $ccServers = @()
    if (Test-Path -LiteralPath $ClaudeJsonPath) {
        try {
            $cj = Get-Content -LiteralPath $ClaudeJsonPath -Raw | ConvertFrom-Json
            if ($cj.mcpServers) { foreach ($p in $cj.mcpServers.PSObject.Properties) { $ccServers += $p.Name } }
            $mcp['claude_json_found'] = $true
        } catch { $mcp['claude_json_read_error'] = $_.Exception.Message }
    } else { $mcp['claude_json_found'] = $false }
    $mcp['claude_code_servers'] = $ccServers

    $desktopServers = @()
    if (Test-Path -LiteralPath $DesktopCfgPath) {
        try {
            $dc = Get-Content -LiteralPath $DesktopCfgPath -Raw | ConvertFrom-Json
            if ($dc.mcpServers) { foreach ($p in $dc.mcpServers.PSObject.Properties) { $desktopServers += $p.Name } }
            $mcp['desktop_config_found'] = $true
        } catch { $mcp['desktop_config_read_error'] = $_.Exception.Message }
    } else { $mcp['desktop_config_found'] = $false }
    $mcp['claude_desktop_servers'] = $desktopServers

    # Log discovery: Claude Desktop logs + Claude Code CLI mcp-logs* dirs (2 levels deep)
    $logResults = @()
    $missingLocations = @()

    if (Test-Path -LiteralPath $DesktopLogsDir) {
        Get-ChildItem -LiteralPath $DesktopLogsDir -Filter '*.log' -File -ErrorAction SilentlyContinue |
            ForEach-Object { $logResults += (Get-LogFact $_) }
    } else { $missingLocations += $DesktopLogsDir }

    if (Test-Path -LiteralPath $CliNodeJsDir) {
        $mcpLogDirs = Get-ChildItem -LiteralPath $CliNodeJsDir -Directory -Recurse -Depth 2 -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -match '^mcp-logs' }
        foreach ($d in $mcpLogDirs) {
            Get-ChildItem -LiteralPath $d.FullName -File -Recurse -ErrorAction SilentlyContinue |
                ForEach-Object { $logResults += (Get-LogFact $_) }
        }
    } else { $missingLocations += $CliNodeJsDir }

    $mcp['log_files'] = $logResults
    $mcp['candidate_locations_not_found'] = $missingLocations
    $facts['mcp'] = $mcp
} catch { $facts['mcp'] = [ordered]@{ error = $_.Exception.Message } }

# --- memory (Check 5) --------------------------------------------------------
try {
    $memory = [ordered]@{}
    $mdFiles = @()
    if (Test-Path -LiteralPath $MemoryDir) {
        Get-ChildItem -LiteralPath $MemoryDir -Filter '*.md' -File -ErrorAction SilentlyContinue | ForEach-Object { $mdFiles += $_.Name }
    }
    $memory['files_on_disk'] = $mdFiles

    $linkedTargets = @()
    if (Test-Path -LiteralPath $MemoryMdPath) {
        foreach ($line in (Get-Content -LiteralPath $MemoryMdPath)) {
            foreach ($m in [regex]::Matches($line, '\(([^)]+\.md)\)')) { $linkedTargets += $m.Groups[1].Value }
        }
    }
    $memory['linked_targets_in_memory_md'] = $linkedTargets
    $facts['memory'] = $memory
} catch { $facts['memory'] = [ordered]@{ error = $_.Exception.Message } }

# --- projects (Check 6) -------------------------------------------------------
try {
    $projects = @()
    if (Test-Path -LiteralPath $ProjectsRoot) {
        foreach ($d in (Get-ChildItem -LiteralPath $ProjectsRoot -Directory -ErrorAction SilentlyContinue)) {
            try {
                $cap = 2000
                $allFiles = @(Get-ChildItem -LiteralPath $d.FullName -File -Recurse -ErrorAction SilentlyContinue | Select-Object -First ($cap + 1))
                $capped = $false
                $fileCount = $allFiles.Count
                if ($fileCount -gt $cap) { $capped = $true; $fileCount = $cap }
                $newest = $null
                if ($allFiles.Count -gt 0) { $newest = ($allFiles | Sort-Object LastWriteTime -Descending | Select-Object -First 1).LastWriteTime.ToString('o') }
                $topFiles = Get-ChildItem -LiteralPath $d.FullName -File -ErrorAction SilentlyContinue
                $projects += [ordered]@{
                    name = $d.Name; file_count = $fileCount; capped = $capped; newest_file_write = $newest
                    has_readme = [bool]($topFiles | Where-Object { $_.Name -match '^README' })
                    has_plan   = [bool]($topFiles | Where-Object { $_.Name -match '^(PLAN|SPEC)' })
                }
            } catch { $projects += [ordered]@{ name = $d.Name; error = $_.Exception.Message } }
        }
    }
    $facts['projects'] = $projects
} catch { $facts['projects'] = @{ error = $_.Exception.Message } }

# --- scripts (Check 7) ---------------------------------------------------------
try {
    $scripts = [ordered]@{}
    if (Test-Path -LiteralPath $ScriptsRoot) {
        $scripts['total_file_count'] = (Get-ChildItem -LiteralPath $ScriptsRoot -File -Recurse -ErrorAction SilentlyContinue | Measure-Object).Count
    } else { $scripts['scripts_root_found'] = $false }
    if (Test-Path -LiteralPath $ScriptsIndexPath) {
        $scripts['scripts_index_exists'] = $true
        $scripts['scripts_index_last_write'] = (Get-Item -LiteralPath $ScriptsIndexPath).LastWriteTime.ToString('o')
    } else { $scripts['scripts_index_exists'] = $false }
    $facts['scripts'] = $scripts
} catch { $facts['scripts'] = [ordered]@{ error = $_.Exception.Message } }

# --- Emit ------------------------------------------------------------------
$json = $facts | ConvertTo-Json -Depth 12
if ($OutFile) { $json | Out-File -LiteralPath $OutFile -Encoding utf8 } else { Write-Output $json }
