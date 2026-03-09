param(
    [int]$DurationHours = 5,
    [int]$IntervalMinutes = 20,
    [int]$HoursWindow = 48
)

$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$reportDir = Join-Path $root "storage\auto-agent-runs"
New-Item -ItemType Directory -Path $reportDir -Force | Out-Null

$endAt = (Get-Date).AddHours($DurationHours)
Write-Host "Auto-improve started. End at: $endAt"

while ((Get-Date) -lt $endAt) {
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $cycleDir = Join-Path $reportDir $stamp
    New-Item -ItemType Directory -Path $cycleDir -Force | Out-Null

    Write-Host "[$stamp] Applying fix recipes..."
    python scripts\auto_fix_recipes.py | Tee-Object -FilePath (Join-Path $cycleDir "fixes.json")

    Write-Host "[$stamp] Syntax check..."
    python -m py_compile app\services\youtube_service.py app\worker\tasks.py app\services\task.py scripts\auto_agent.py scripts\auto_fix_recipes.py 2>&1 | Tee-Object -FilePath (Join-Path $cycleDir "py_compile.log")

    Write-Host "[$stamp] Running agent audit..."
    python scripts\auto_agent.py --hours $HoursWindow --output (Join-Path $cycleDir "report.md") | Tee-Object -FilePath (Join-Path $cycleDir "summary.json")

    Write-Host "[$stamp] Sleeping $IntervalMinutes minutes..."
    Start-Sleep -Seconds ($IntervalMinutes * 60)
}

Write-Host "Auto-improve completed."
