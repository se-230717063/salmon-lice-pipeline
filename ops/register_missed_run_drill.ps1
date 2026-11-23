$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$scriptPath = Join-Path $PSScriptRoot 'missed_run_drill.ps1'
$identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$principal = New-ScheduledTaskPrincipal -UserId $identity -LogonType S4U -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -WakeToRun -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 10)
$phases = @(
    @{Name='begin'; At=[datetime]'2026-11-24T19:55:00'},
    @{Name='resume'; At=[datetime]'2026-11-25T19:55:00'},
    @{Name='finish'; At=[datetime]'2026-11-25T20:50:00'}
)
foreach ($phase in $phases) {
    $name = 'SalmonLiceDrill-' + $phase.Name
    $action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument ('-NoProfile -ExecutionPolicy Bypass -File "'+$scriptPath+'" -Phase '+$phase.Name) -WorkingDirectory $projectRoot
    $trigger = New-ScheduledTaskTrigger -Once -At $phase.At
    $task = New-ScheduledTask -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description 'One-off M5 missed-run experiment; never disables the independent monitor.'
    Register-ScheduledTask -TaskName $name -InputObject $task -Force -ErrorAction Stop | Out-Null
    Export-ScheduledTask -TaskName $name -ErrorAction Stop | Set-Content -LiteralPath (Join-Path $PSScriptRoot ('drill_'+$phase.Name+'.xml')) -Encoding Unicode
}
