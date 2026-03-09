param(
    [int]$DurationHours = 5,
    [int]$IntervalMinutes = 20,
    [int]$HoursWindow = 48,
    [int]$MaxUploadsPerCycle = 2,
    [string]$Mode = "default",
    [string]$AOProject = "MoneyPrinterTurbo",
    [switch]$WithAO,
    [switch]$AOStartIfNeeded,
    [switch]$AONoDashboard
)

$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$runDir = Join-Path $root "storage\ao-loop-runs"
New-Item -ItemType Directory -Path $runDir -Force | Out-Null

$endAt = (Get-Date).AddHours($DurationHours)
Write-Host "AO autopilot started. End at: $endAt"

while ((Get-Date) -lt $endAt) {
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $cycleDir = Join-Path $runDir $stamp
    New-Item -ItemType Directory -Path $cycleDir -Force | Out-Null

    $cmd = @(
        "scripts\ao_auto_orchestrator.py",
        "--hours", $HoursWindow,
        "--max-uploads", $MaxUploadsPerCycle,
        "--mode", $Mode,
        "--ao-project", $AOProject
    )

    if ($WithAO) {
        $cmd += "--with-ao"
    }
    if ($AOStartIfNeeded) {
        $cmd += "--ao-start-if-needed"
    }
    if ($AONoDashboard) {
        $cmd += "--ao-no-dashboard"
    }

    python @cmd | Tee-Object -FilePath (Join-Path $cycleDir "summary.json")
    Start-Sleep -Seconds ($IntervalMinutes * 60)
}

Write-Host "AO autopilot completed."
