param(
    [ValidateSet("start", "status", "stop", "run-once")]
    [string]$Action = "start",
    [switch]$PreferAO,
    [string]$AOProject = "MoneyPrinterTurbo"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$runnerScript = Join-Path $PSScriptRoot "windows_agent_runner.ps1"
$runnerConfig = Join-Path $PSScriptRoot "windows_agent_runner.config.json"
$aoConfig = Join-Path $root "agent-orchestrator.yaml"
$homeDir = Join-Path $root "storage\agent-orchestrator\home"
$tmuxWinGetDir = "C:\Users\DINH MANH\AppData\Local\Microsoft\WinGet\Packages\arndawg.tmux-windows_Microsoft.Winget.Source_8wekyb3d8bbwe"

function Test-Command {
    param([string]$Name)
    try {
        return $null -ne (Get-Command $Name -ErrorAction Stop)
    } catch {
        return $false
    }
}

function Add-PathHead {
    param([string]$Dir)
    if (-not (Test-Path -LiteralPath $Dir)) {
        return
    }
    $parts = ($env:PATH -split ";") | Where-Object { $_ -and $_.Trim() }
    if ($parts -contains $Dir) {
        return
    }
    $env:PATH = "$Dir;$env:PATH"
}

function Test-TmuxReady {
    $tmuxCandidates = @(
        (Join-Path $tmuxWinGetDir "tmux.exe"),
        "tmux.exe"
    )
    foreach ($candidate in $tmuxCandidates) {
        try {
            & $candidate -V | Out-Null
            return $true
        } catch {
        }
    }
    return $false
}

function Test-AOHealth {
    if (-not (Test-Path -LiteralPath $aoConfig)) {
        return @{ ok = $false; reason = "missing agent-orchestrator.yaml" }
    }
    if (-not (Test-Command "ao.cmd")) {
        return @{ ok = $false; reason = "ao.cmd not found" }
    }
    if (-not (Test-TmuxReady)) {
        return @{ ok = $false; reason = "tmux not available" }
    }
    if (-not (Test-Command "claude.exe") -and -not (Test-Command "codex.cmd")) {
        return @{ ok = $false; reason = "no agent CLI (claude.exe/codex.cmd)" }
    }
    return @{ ok = $true; reason = "ready" }
}

function Invoke-AO {
    param([ValidateSet("start", "status", "stop")] [string]$AoAction)

    New-Item -ItemType Directory -Path $homeDir -Force | Out-Null
    $env:HOME = $homeDir
    $env:USERPROFILE = $homeDir

    Add-PathHead -Dir $tmuxWinGetDir
    Add-PathHead -Dir "C:\Users\DINH MANH\.local\bin"
    Add-PathHead -Dir "C:\Program Files\Git\usr\bin"
    Add-PathHead -Dir "C:\Program Files\Git\cmd"
    Add-PathHead -Dir "C:\Users\myname\AppData\Roaming\npm"

    if ($AoAction -eq "start") {
        ao.cmd start $AOProject --no-dashboard
        return
    }
    if ($AoAction -eq "stop") {
        ao.cmd stop $AOProject
        return
    }
    ao.cmd status
}

function Test-AOSessionStable {
    try {
        $statusText = (ao.cmd status | Out-String)
        $sessionText = (ao.cmd session ls -p $AOProject | Out-String)
        $hasSession = $sessionText -match "orchestrator"
        if (-not $hasSession) {
            return $false
        }
        if ($statusText -match "exited" -or $sessionText -match "\[killed\]") {
            return $false
        }
        return $true
    } catch {
        return $false
    }
}

function Invoke-Runner {
    param([ValidateSet("start", "status", "stop", "run-once")] [string]$RunnerAction)

    if ($RunnerAction -eq "start") {
        & powershell -NoProfile -ExecutionPolicy Bypass -File $runnerScript -Action start -ConfigPath $runnerConfig
        return
    }
    if ($RunnerAction -eq "status") {
        & powershell -NoProfile -ExecutionPolicy Bypass -File $runnerScript -Action status -ConfigPath $runnerConfig
        return
    }
    if ($RunnerAction -eq "run-once") {
        & powershell -NoProfile -ExecutionPolicy Bypass -File $runnerScript -Action run-once -ConfigPath $runnerConfig
        return
    }
    & powershell -NoProfile -ExecutionPolicy Bypass -File $runnerScript -Action stop -ConfigPath $runnerConfig
}

switch ($Action) {
    "status" {
        $ao = Test-AOHealth
        [pscustomobject]@{
            ao_ready = $ao.ok
            ao_reason = $ao.reason
            prefer_ao = [bool]$PreferAO
        } | ConvertTo-Json -Depth 4
        if ($ao.ok) {
            try { Invoke-AO -AoAction status } catch { Write-Warning $_.Exception.Message }
        }
        Invoke-Runner -RunnerAction status
        break
    }
    "stop" {
        $ao = Test-AOHealth
        if ($ao.ok) {
            try { Invoke-AO -AoAction stop } catch { Write-Warning $_.Exception.Message }
        }
        Invoke-Runner -RunnerAction stop
        break
    }
    "run-once" {
        Invoke-Runner -RunnerAction run-once
        break
    }
    default {
        $ao = Test-AOHealth
        if ($PreferAO -and $ao.ok) {
            try {
                Invoke-AO -AoAction start
                Start-Sleep -Seconds 2
                if (-not (Test-AOSessionStable)) {
                    Write-Warning "AO session exited quickly, fallback to windows runner."
                    Invoke-Runner -RunnerAction start
                }
                break
            } catch {
                Write-Warning "AO start failed, fallback to windows runner: $($_.Exception.Message)"
            }
        }
        Invoke-Runner -RunnerAction start
        break
    }
}
