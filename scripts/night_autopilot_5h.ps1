param(
    [int]$DurationHours = 5,
    [int]$IntervalMinutes = 20,
    [int]$HoursWindow = 72,
    [int]$MinFreeRamMB = 1800,
    [int]$MaxUploadsPerCycle = 2
)

$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$runDir = Join-Path $root "storage\night-autopilot-runs"
New-Item -ItemType Directory -Path $runDir -Force | Out-Null

$endAt = (Get-Date).AddHours($DurationHours)
Write-Host "Night autopilot started. End at: $endAt"

while ((Get-Date) -lt $endAt) {
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $cycleDir = Join-Path $runDir $stamp
    New-Item -ItemType Directory -Path $cycleDir -Force | Out-Null

    $os = Get-CimInstance Win32_OperatingSystem
    $freeRamMB = [int]($os.FreePhysicalMemory / 1024)
    "free_ram_mb=$freeRamMB" | Set-Content (Join-Path $cycleDir "ram.txt")

    if ($freeRamMB -lt $MinFreeRamMB) {
        "SKIP cycle: low RAM ($freeRamMB MB < $MinFreeRamMB MB)" | Set-Content (Join-Path $cycleDir "skip.txt")
        Start-Sleep -Seconds ($IntervalMinutes * 60)
        continue
    }

    python scripts\auto_fix_recipes.py | Tee-Object -FilePath (Join-Path $cycleDir "fixes.json")
    python -m py_compile app\services\youtube_service.py app\worker\tasks.py app\services\task.py scripts\auto_agent.py scripts\auto_fix_recipes.py scripts\auto_upload_candidates.py 2>&1 | Tee-Object -FilePath (Join-Path $cycleDir "py_compile.log")
    python scripts\auto_agent.py --hours $HoursWindow --output (Join-Path $cycleDir "report.md") | Tee-Object -FilePath (Join-Path $cycleDir "summary.json")
    python scripts\auto_upload_candidates.py --max $MaxUploadsPerCycle | Tee-Object -FilePath (Join-Path $cycleDir "uploads.json")

    Start-Sleep -Seconds ($IntervalMinutes * 60)
}

Write-Host "Night autopilot completed."
