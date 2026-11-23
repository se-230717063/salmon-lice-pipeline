$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
$identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$action = New-ScheduledTaskAction -Execute $pythonPath -Argument 'src\monitor.py' -WorkingDirectory $projectRoot
$triggers = @((New-ScheduledTaskTrigger -Daily -At '15:50'),(New-ScheduledTaskTrigger -Daily -At '20:50'))
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -WakeToRun -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 5)
$principal = New-ScheduledTaskPrincipal -UserId $identity -LogonType S4U -RunLevel Limited
$task = New-ScheduledTask -Action $action -Trigger $triggers -Settings $settings -Principal $principal -Description 'Independent M5 monitor; continues even if the pipeline task is disabled.'
Register-ScheduledTask -TaskName 'SalmonLiceMonitor' -InputObject $task -Force -ErrorAction Stop | Out-Null
Export-ScheduledTask -TaskName 'SalmonLiceMonitor' -ErrorAction Stop | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'monitor_scheduler.xml') -Encoding Unicode
$info = Get-ScheduledTaskInfo -TaskName 'SalmonLiceMonitor' -ErrorAction Stop
Write-Output ('Monitor next run: '+$info.NextRunTime.ToString('o'))
