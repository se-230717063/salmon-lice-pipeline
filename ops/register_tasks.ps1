# Register under the current Windows identity; no passwords are stored in this file.
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Project venv not found' }
$identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$action = New-ScheduledTaskAction -Execute $pythonPath -Argument 'src\run_pipeline.py --kind scheduled' -WorkingDirectory $projectRoot
$triggers = @(
    (New-ScheduledTaskTrigger -Daily -At '15:15'),
    (New-ScheduledTaskTrigger -Daily -At '20:15')
)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -WakeToRun -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 3)
$principal = New-ScheduledTaskPrincipal -UserId $identity -LogonType S4U -RunLevel Limited
$task = New-ScheduledTask -Action $action -Trigger $triggers -Settings $settings -Principal $principal -Description 'Salmon lice M5 pipeline; daily 15:15 and 20:15 local time, missed starts recovered.'
Register-ScheduledTask -TaskName 'SalmonLicePipeline' -InputObject $task -Force -ErrorAction Stop | Out-Null
Export-ScheduledTask -TaskName 'SalmonLicePipeline' -ErrorAction Stop | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'task_scheduler.xml') -Encoding Unicode
Get-ScheduledTaskInfo -TaskName 'SalmonLicePipeline' -ErrorAction Stop | Select-Object LastRunTime,NextRunTime,LastTaskResult
