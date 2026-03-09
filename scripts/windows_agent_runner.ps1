param(
    [ValidateSet("run", "run-once", "start", "status", "pause", "resume", "stop", "clear-flags", "unlock")]
    [string]$Action = "status",
    [string]$ConfigPath = "",
    [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$script:RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $script:RepoRoot

if (-not $ConfigPath) {
    $ConfigPath = Join-Path $PSScriptRoot "windows_agent_runner.config.json"
}

function Resolve-RepoPath {
    param([Parameter(Mandatory = $true)][string]$PathValue)

    if ([System.IO.Path]::IsPathRooted($PathValue)) {
        return $PathValue
    }
    return Join-Path $script:RepoRoot $PathValue
}

function Read-RunnerConfig {
    param([Parameter(Mandatory = $true)][string]$PathValue)

    if (-not (Test-Path -LiteralPath $PathValue)) {
        throw "Runner config not found: $PathValue"
    }

    return Get-Content -LiteralPath $PathValue -Raw | ConvertFrom-Json
}

function New-RunnerPaths {
    param([Parameter(Mandatory = $true)]$Config)

    $runnerRoot = Resolve-RepoPath -PathValue $Config.runnerRoot
    return @{
        RunnerRoot = $runnerRoot
        StateFile = Join-Path $runnerRoot "state.json"
        LockFile = Join-Path $runnerRoot "lock.json"
        PauseFlag = Join-Path $runnerRoot "pause.flag"
        StopFlag = Join-Path $runnerRoot "stop.flag"
        RunnerLog = Join-Path $runnerRoot "runner.log"
        CyclesDir = Join-Path $runnerRoot "cycles"
    }
}

function Initialize-RunnerLayout {
    param([Parameter(Mandatory = $true)][hashtable]$Paths)

    foreach ($dir in @($Paths.RunnerRoot, $Paths.CyclesDir)) {
        if (-not (Test-Path -LiteralPath $dir)) {
            New-Item -ItemType Directory -Path $dir -Force | Out-Null
        }
    }
}

function Write-RunnerLog {
    param(
        [Parameter(Mandatory = $true)][hashtable]$Paths,
        [Parameter(Mandatory = $true)][string]$Message,
        [string]$Level = "INFO"
    )

    $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$stamp][$Level] $Message"
    Write-Host $line
    Add-Content -LiteralPath $Paths.RunnerLog -Value $line
}

function Save-JsonFile {
    param(
        [Parameter(Mandatory = $true)][string]$PathValue,
        [Parameter(Mandatory = $true)]$Data
    )

    $json = $Data | ConvertTo-Json -Depth 8
    Set-Content -LiteralPath $PathValue -Value $json -Encoding UTF8
}

function Read-JsonFile {
    param([Parameter(Mandatory = $true)][string]$PathValue)

    if (-not (Test-Path -LiteralPath $PathValue)) {
        return $null
    }
    return Get-Content -LiteralPath $PathValue -Raw | ConvertFrom-Json
}

function Test-ProcessActive {
    param([int]$ProcessId)

    if ($ProcessId -le 0) {
        return $false
    }

    return $null -ne (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue)
}

function Get-LockInfo {
    param([Parameter(Mandatory = $true)][hashtable]$Paths)
    return Read-JsonFile -PathValue $Paths.LockFile
}

function Acquire-RunnerLock {
    param(
        [Parameter(Mandatory = $true)][hashtable]$Paths,
        [switch]$Force
    )

    $existing = Get-LockInfo -Paths $Paths
    if ($null -ne $existing -and (Test-ProcessActive -ProcessId ([int]$existing.pid)) -and -not $Force) {
        throw "Runner already active with PID $($existing.pid). Use -Action status or -Action unlock -Force."
    }

    $payload = @{
        pid = $PID
        acquired_at = (Get-Date).ToString("o")
        host = $env:COMPUTERNAME
        script = $PSCommandPath
    }
    Save-JsonFile -PathValue $Paths.LockFile -Data $payload
}

function Release-RunnerLock {
    param([Parameter(Mandatory = $true)][hashtable]$Paths)

    if (Test-Path -LiteralPath $Paths.LockFile) {
        Remove-Item -LiteralPath $Paths.LockFile -Force
    }
}

function Update-RunnerState {
    param(
        [Parameter(Mandatory = $true)][hashtable]$Paths,
        [Parameter(Mandatory = $true)]$State
    )

    Save-JsonFile -PathValue $Paths.StateFile -Data $State
}

function Get-RunnerState {
    param([Parameter(Mandatory = $true)][hashtable]$Paths)
    return Read-JsonFile -PathValue $Paths.StateFile
}

function Set-RunnerFlag {
    param(
        [Parameter(Mandatory = $true)][string]$PathValue,
        [Parameter(Mandatory = $true)][string]$Content
    )

    Set-Content -LiteralPath $PathValue -Value $Content -Encoding UTF8
}

function Clear-RunnerFlag {
    param([Parameter(Mandatory = $true)][string]$PathValue)

    if (Test-Path -LiteralPath $PathValue) {
        Remove-Item -LiteralPath $PathValue -Force
    }
}

function Invoke-LoggedProcess {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$ArgumentList,
        [Parameter(Mandatory = $true)][string]$CycleDir,
        [int]$TimeoutSeconds = 1800
    )

    $stdoutPath = Join-Path $CycleDir "$Name.stdout.log"
    $stderrPath = Join-Path $CycleDir "$Name.stderr.log"
    $startedAt = Get-Date

    $process = Start-Process `
        -FilePath $FilePath `
        -ArgumentList $ArgumentList `
        -WorkingDirectory $script:RepoRoot `
        -RedirectStandardOutput $stdoutPath `
        -RedirectStandardError $stderrPath `
        -PassThru `
        -NoNewWindow

    if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
        try {
            $process.Kill()
        } catch {
        }
        return @{
            name = $Name
            ok = $false
            exit_code = -1
            timed_out = $true
            started_at = $startedAt.ToString("o")
            finished_at = (Get-Date).ToString("o")
            stdout_log = $stdoutPath
            stderr_log = $stderrPath
        }
    }

    $exitCode = $process.ExitCode
    if ($null -eq $exitCode) {
        # Some Windows process hosts may report null despite completed execution.
        # Treat as success unless timeout occurred.
        $exitCode = 0
    }

    return @{
        name = $Name
        ok = ($exitCode -eq 0)
        exit_code = $exitCode
        timed_out = $false
        started_at = $startedAt.ToString("o")
        finished_at = (Get-Date).ToString("o")
        stdout_log = $stdoutPath
        stderr_log = $stderrPath
    }
}

function Invoke-CommandStep {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$CommandText,
        [Parameter(Mandatory = $true)][string]$CycleDir,
        [int]$TimeoutSeconds = 1800
    )

    return Invoke-LoggedProcess `
        -Name $Name `
        -FilePath "powershell.exe" `
        -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $CommandText) `
        -CycleDir $CycleDir `
        -TimeoutSeconds $TimeoutSeconds
}

function Get-GitSnapshot {
    $statusLines = @()
    $diffStatLines = @()

    try {
        $statusLines = @(git status --short 2>$null)
    } catch {
        $statusLines = @("git status failed: $($_.Exception.Message)")
    }

    try {
        $diffStatLines = @(git diff --stat 2>$null)
    } catch {
        $diffStatLines = @("git diff --stat failed: $($_.Exception.Message)")
    }

    return @{
        status = $statusLines
        diff_stat = $diffStatLines
    }
}

function Invoke-AgentCycle {
    param(
        [Parameter(Mandatory = $true)]$Config,
        [Parameter(Mandatory = $true)][hashtable]$Paths,
        [int]$CycleNumber
    )

    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $cycleDir = Join-Path $Paths.CyclesDir $stamp
    New-Item -ItemType Directory -Path $cycleDir -Force | Out-Null

    $state = @{
        status = "running"
        pid = $PID
        cycle = $CycleNumber
        cycle_id = $stamp
        started_at = (Get-Date).ToString("o")
        config_path = $ConfigPath
        last_message = "Cycle started"
    }
    Update-RunnerState -Paths $Paths -State $state

    $pythonExe = if ($Config.python) { [string]$Config.python } else { "python" }
    $stepTimeout = if ($Config.stepTimeoutSeconds) { [int]$Config.stepTimeoutSeconds } else { 1800 }
    $stopOnStepFailure = $true
    if ($null -ne $Config.stopOnStepFailure) {
        $stopOnStepFailure = [bool]$Config.stopOnStepFailure
    }

    $summary = @{
        cycle = $CycleNumber
        cycle_id = $stamp
        started_at = (Get-Date).ToString("o")
        repo_root = $script:RepoRoot
        config_path = $ConfigPath
        git_before = Get-GitSnapshot
        steps = @()
    }

    $steps = New-Object System.Collections.Generic.List[object]

    if ($Config.steps.applyFixRecipes) {
        $steps.Add(@{
            name = "fix_recipes"
            kind = "process"
            file = $pythonExe
            args = @("scripts/auto_fix_recipes.py")
        })
    }

    if ($Config.steps.compileCheck) {
        $compileArgs = @("-m", "py_compile")
        foreach ($target in $Config.compileTargets) {
            $compileArgs += [string]$target
        }
        $steps.Add(@{
            name = "compile_check"
            kind = "process"
            file = $pythonExe
            args = $compileArgs
        })
    }

    if ($Config.steps.runAudit) {
        $auditOutput = Join-Path $cycleDir "report.md"
        $steps.Add(@{
            name = "audit"
            kind = "process"
            file = $pythonExe
            args = @("scripts/auto_agent.py", "--hours", [string]$Config.auditHoursWindow, "--output", $auditOutput)
        })
    }

    $agentCommand = ""
    if ($Config.agentCommand) {
        $agentCommand = [string]$Config.agentCommand
    }
    if ($Config.steps.runAgentCommand -and $agentCommand.Trim()) {
        $steps.Add(@{
            name = "agent_command"
            kind = "command"
            command = $agentCommand
        })
    }

    foreach ($step in $steps) {
        $state.last_message = "Running step: $($step.name)"
        Update-RunnerState -Paths $Paths -State $state
        Write-RunnerLog -Paths $Paths -Message "Cycle $CycleNumber step $($step.name) started."

        if ($step.kind -eq "process") {
            $result = Invoke-LoggedProcess `
                -Name $step.name `
                -FilePath ([string]$step.file) `
                -ArgumentList $step.args `
                -CycleDir $cycleDir `
                -TimeoutSeconds $stepTimeout
        } else {
            $result = Invoke-CommandStep `
                -Name $step.name `
                -CommandText ([string]$step.command) `
                -CycleDir $cycleDir `
                -TimeoutSeconds $stepTimeout
        }

        $summary.steps += $result

        if (-not $result.ok) {
            Write-RunnerLog -Paths $Paths -Message "Cycle $CycleNumber step $($step.name) failed with exit code $($result.exit_code)." -Level "WARN"
            if ($stopOnStepFailure) {
                break
            }
        } else {
            Write-RunnerLog -Paths $Paths -Message "Cycle $CycleNumber step $($step.name) completed."
        }
    }

    $summary.git_after = Get-GitSnapshot
    $summary.finished_at = (Get-Date).ToString("o")
    $summary.success = -not ($summary.steps | Where-Object { -not $_.ok } | Select-Object -First 1)
    Save-JsonFile -PathValue (Join-Path $cycleDir "summary.json") -Data $summary

    $state.status = if ($summary.success) { "idle" } else { "warning" }
    $state.last_cycle = $stamp
    $state.last_cycle_dir = $cycleDir
    $state.last_finished_at = $summary.finished_at
    $state.last_message = if ($summary.success) { "Cycle completed" } else { "Cycle completed with failures" }
    Update-RunnerState -Paths $Paths -State $state

    return $summary
}

function Show-RunnerStatus {
    param([Parameter(Mandatory = $true)][hashtable]$Paths)

    $state = Get-RunnerState -Paths $Paths
    $lock = Get-LockInfo -Paths $Paths
    $status = [ordered]@{
        runner_root = $Paths.RunnerRoot
        state_file = $Paths.StateFile
        lock_active = $false
        pause_flag = (Test-Path -LiteralPath $Paths.PauseFlag)
        stop_flag = (Test-Path -LiteralPath $Paths.StopFlag)
    }

    if ($null -ne $lock) {
        $status.lock = $lock
        $status.lock_active = Test-ProcessActive -ProcessId ([int]$lock.pid)
    }

    if ($null -ne $state) {
        $status.state = $state
    }

    $status | ConvertTo-Json -Depth 8
}

function Start-DetachedRunner {
    param([Parameter(Mandatory = $true)][string]$ConfigPathValue)

    $psExe = (Get-Process -Id $PID).Path
    $args = @(
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        $PSCommandPath,
        "-Action",
        "run",
        "-ConfigPath",
        $ConfigPathValue
    )
    if ($Force) {
        $args += "-Force"
    }

    $proc = Start-Process -FilePath $psExe -ArgumentList $args -WorkingDirectory $script:RepoRoot -WindowStyle Hidden -PassThru
    return @{
        started = $true
        pid = $proc.Id
        config_path = $ConfigPathValue
    }
}

$config = Read-RunnerConfig -PathValue $ConfigPath
$paths = New-RunnerPaths -Config $config
Initialize-RunnerLayout -Paths $paths

switch ($Action) {
    "status" {
        Show-RunnerStatus -Paths $paths
        break
    }
    "pause" {
        Set-RunnerFlag -PathValue $paths.PauseFlag -Content "paused $(Get-Date -Format o)"
        Write-RunnerLog -Paths $paths -Message "Pause flag set."
        Show-RunnerStatus -Paths $paths
        break
    }
    "resume" {
        Clear-RunnerFlag -PathValue $paths.PauseFlag
        Write-RunnerLog -Paths $paths -Message "Pause flag cleared."
        Show-RunnerStatus -Paths $paths
        break
    }
    "stop" {
        Set-RunnerFlag -PathValue $paths.StopFlag -Content "stop requested $(Get-Date -Format o)"
        Write-RunnerLog -Paths $paths -Message "Stop flag set."
        Show-RunnerStatus -Paths $paths
        break
    }
    "clear-flags" {
        Clear-RunnerFlag -PathValue $paths.PauseFlag
        Clear-RunnerFlag -PathValue $paths.StopFlag
        Write-RunnerLog -Paths $paths -Message "Control flags cleared."
        Show-RunnerStatus -Paths $paths
        break
    }
    "unlock" {
        $lock = Get-LockInfo -Paths $paths
        if ($null -eq $lock) {
            Write-Host "No lock file present."
            break
        }
        if ((Test-ProcessActive -ProcessId ([int]$lock.pid)) -and -not $Force) {
            throw "Lock is still active for PID $($lock.pid). Use -Force only if you know the runner is stale."
        }
        Release-RunnerLock -Paths $paths
        Write-RunnerLog -Paths $paths -Message "Lock file removed."
        break
    }
    "start" {
        $result = Start-DetachedRunner -ConfigPathValue $ConfigPath
        $result | ConvertTo-Json -Depth 5
        break
    }
    default {
        Acquire-RunnerLock -Paths $paths -Force:$Force
        try {
            $intervalSeconds = if ($config.intervalSeconds) { [int]$config.intervalSeconds } else { 900 }
            $pauseSeconds = if ($config.pauseSeconds) { [int]$config.pauseSeconds } else { 15 }
            $maxCycles = if ($config.maxCycles) { [int]$config.maxCycles } else { 0 }

            $state = @{
                status = "running"
                pid = $PID
                started_at = (Get-Date).ToString("o")
                config_path = $ConfigPath
                last_message = "Runner started"
            }
            Update-RunnerState -Paths $paths -State $state
            Write-RunnerLog -Paths $paths -Message "Runner started with action '$Action'."

            $cycle = 0
            do {
                if (Test-Path -LiteralPath $paths.StopFlag) {
                    Write-RunnerLog -Paths $paths -Message "Stop flag detected. Exiting runner."
                    break
                }

                if (Test-Path -LiteralPath $paths.PauseFlag) {
                    $state.status = "paused"
                    $state.last_message = "Pause flag detected"
                    Update-RunnerState -Paths $paths -State $state
                    Start-Sleep -Seconds $pauseSeconds
                    continue
                }

                $cycle++
                $summary = Invoke-AgentCycle -Config $config -Paths $paths -CycleNumber $cycle
                if ($Action -eq "run-once") {
                    $summary | ConvertTo-Json -Depth 8
                    break
                }

                if ($maxCycles -gt 0 -and $cycle -ge $maxCycles) {
                    Write-RunnerLog -Paths $paths -Message "Max cycle limit $maxCycles reached."
                    break
                }

                $state = Get-RunnerState -Paths $paths
                $state.status = "sleeping"
                $state.last_message = "Sleeping for $intervalSeconds seconds"
                Update-RunnerState -Paths $paths -State $state
                Start-Sleep -Seconds $intervalSeconds
            } while ($true)
        } finally {
            $finalState = Get-RunnerState -Paths $paths
            if ($null -eq $finalState) {
                $finalState = @{}
            }
            $finalState.status = "stopped"
            $finalState.stopped_at = (Get-Date).ToString("o")
            $finalState.last_message = "Runner stopped"
            Update-RunnerState -Paths $paths -State $finalState
            Release-RunnerLock -Paths $paths
            Write-RunnerLog -Paths $paths -Message "Runner stopped."
        }
        break
    }
}
