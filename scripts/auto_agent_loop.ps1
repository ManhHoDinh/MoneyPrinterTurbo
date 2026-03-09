param(
    [int]$IntervalMinutes = 30,
    [int]$HoursWindow = 48
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "Auto-agent loop started. Interval=$IntervalMinutes min, Window=$HoursWindow h"

while ($true) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$ts] Running auto-agent..."
    python scripts\auto_agent.py --hours $HoursWindow
    Start-Sleep -Seconds ($IntervalMinutes * 60)
}
