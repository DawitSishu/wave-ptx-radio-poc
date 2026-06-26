<#
  Switch to the CUSTOM system (no Radio.co) and make it permanent:
    - ensures settings.yaml has audio_dir + schedule_file (the engine needs them)
    - WavePTX-Engine    : the schedule-driven broadcaster (dashboard -> audio -> VB-Cable),
                          auto-starts at logon, auto-restarts
    - WavePTX-Dashboard : the web UI on :8080, auto-starts at logon, auto-restarts
    - disables WavePTX-Relay (the Radio.co source) so only one drives VB-Cable
    - WavePTX-Watchdog keeps monitoring the heartbeat (the engine writes it now)

  Run ONLY after you've tested the engine + put real prompts in the dashboard, since
  this makes the engine the live broadcaster (off Radio.co).

    powershell -ExecutionPolicy Bypass -File setup_custom.ps1
#>
param(
  [string]$User = "waveadmin",
  [string]$Root = "C:\wave-poc"
)
$ErrorActionPreference = "Stop"
$py = "C:\Program Files\Python312\python.exe"
if (-not (Test-Path $py)) { $py = (Get-Command python).Source }

# ensure the engine's required paths are in settings.yaml (preserve everything else)
& $py -c "import yaml; p=r'C:\wave-poc\config\settings.yaml'; s=yaml.safe_load(open(p,encoding='utf-8')) or {}; s['audio_dir']='C:/wave-poc/audio'; s['schedule_file']='C:/wave-poc/config/schedule.yaml'; yaml.safe_dump(s,open(p,'w',encoding='utf-8'),sort_keys=False); print('settings updated for engine')"

$pr = New-ScheduledTaskPrincipal -UserId $User -RunLevel Highest -LogonType Interactive
$set = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
        -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
        -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew

# WavePTX-Engine (custom broadcaster)
$aE = New-ScheduledTaskAction -Execute $py -Argument "`"$Root\src\engine.py`" `"$Root\config\settings.yaml`"" -WorkingDirectory $Root
Register-ScheduledTask -TaskName "WavePTX-Engine" -Action $aE -Trigger (New-ScheduledTaskTrigger -AtLogOn -User $User) -Principal $pr -Settings $set -Force | Out-Null
Write-Host "Registered: WavePTX-Engine (custom broadcaster)"

# WavePTX-Dashboard (web UI :8080)
$aD = New-ScheduledTaskAction -Execute $py -Argument "`"$Root\web\app.py`"" -WorkingDirectory $Root
Register-ScheduledTask -TaskName "WavePTX-Dashboard" -Action $aD -Trigger (New-ScheduledTaskTrigger -AtLogOn -User $User) -Principal $pr -Settings $set -Force | Out-Null
Write-Host "Registered: WavePTX-Dashboard (web UI on :8080)"

# Disable the Radio.co relay - the custom engine is the broadcaster now
Stop-ScheduledTask    -TaskName "WavePTX-Relay" -ErrorAction SilentlyContinue
Disable-ScheduledTask -TaskName "WavePTX-Relay" -ErrorAction SilentlyContinue | Out-Null
Write-Host "Disabled: WavePTX-Relay (Radio.co source)"

Write-Host "`n=== CUSTOM SYSTEM IS LIVE ===" -ForegroundColor Green
Write-Host "Engine + Dashboard auto-start at logon; the watchdog monitors the engine heartbeat."
Write-Host "Reboot to verify:  Restart-Computer -Force"
Write-Host "Permanent public URL = a named Cloudflare tunnel (needs a free CF account); ask to set it up."
