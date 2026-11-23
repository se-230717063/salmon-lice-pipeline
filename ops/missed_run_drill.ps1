param([Parameter(Mandatory=$true)][ValidateSet('begin','resume','finish')][string]$Phase)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
$statePath = Join-Path $projectRoot 'data\missed_drill_state.json'
$nowLocal = Get-Date
if ($Phase -eq 'begin') {
    # A late catch-up must never disable the pipeline after the planned experiment.
    if ($nowLocal -lt [datetime]'2026-11-24T19:55:00' -or $nowLocal -ge [datetime]'2026-11-24T20:10:00') { throw 'Outside safe experiment-start window; pipeline not disabled' }
    & $pythonPath -X utf8 notebooks/m5_missed_run_capture.py before
    if ($LASTEXITCODE -ne 0) { throw 'Before capture failed; pipeline not disabled' }
    $task = Get-ScheduledTask -TaskName 'SalmonLicePipeline' -ErrorAction Stop
    $oldCatchup = $task.Settings.StartWhenAvailable
    $task.Settings.StartWhenAvailable = $false
    Set-ScheduledTask -TaskName 'SalmonLicePipeline' -Settings $task.Settings -ErrorAction Stop | Out-Null
    Disable-ScheduledTask -TaskName 'SalmonLicePipeline' -ErrorAction Stop | Out-Null
    @{phase='disabled';began_at=$nowLocal.ToUniversalTime().ToString('o');restore_catchup=$oldCatchup} | ConvertTo-Json | Set-Content -LiteralPath $statePath -Encoding UTF8
} elseif ($Phase -eq 'resume') {
    # Always re-enable; this remains safe even if the begin task did not execute.
    Enable-ScheduledTask -TaskName 'SalmonLicePipeline' -ErrorAction Stop | Out-Null
    if (Test-Path -LiteralPath $statePath) {
        $state = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
        $state.phase = 'resumed'
        $state | Add-Member -NotePropertyName resumed_at -NotePropertyValue $nowLocal.ToUniversalTime().ToString('o') -Force
        $state | ConvertTo-Json | Set-Content -LiteralPath $statePath -Encoding UTF8
    }
} else {
    try {
        & $pythonPath -X utf8 notebooks/m5_missed_run_capture.py after
        if ($LASTEXITCODE -ne 0) { throw 'Recovery not verified; inspect logs and rerun capture after a successful scheduled run' }
    } finally {
        # Restore normal missed-start recovery regardless of experiment outcome.
        $task = Get-ScheduledTask -TaskName 'SalmonLicePipeline' -ErrorAction Stop
        $task.Settings.StartWhenAvailable = $true
        Set-ScheduledTask -TaskName 'SalmonLicePipeline' -Settings $task.Settings -ErrorAction Stop | Out-Null
        Enable-ScheduledTask -TaskName 'SalmonLicePipeline' -ErrorAction Stop | Out-Null
    }
}
