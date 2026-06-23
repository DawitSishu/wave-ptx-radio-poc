<#
  Make the Radio.co STREAM RELAY the 24/7 service (replacing the old local-file engine).

    - registers  WavePTX-Relay   : runs radioco_relay.py at logon, auto-restarts if it dies
    - disables   WavePTX-Engine  : the old local-file scheduler (so they don't both
                                    drive VB-Cable at once)
    - keeps      WavePTX-Watchdog: already alerts to Slack if the heartbeat goes stale —
                                    and the relay now writes that heartbeat

  Autologon + never-sleep power were already set by setup_service.ps1.

  Run once, as administrator:
    powershell -ExecutionPolicy Bypass -File setup_relay_service.ps1
#>
param(
  [string]$StationId = "s62f446ec2",
  [string]$User = "waveadmin",
  [string]$Root = "C:\wave-poc"
)
$ErrorActionPreference = "Stop"

$py = "C:\Program Files\Python312\python.exe"
if (-not (Test-Path $py)) { $py = (Get-Command python).Source }
Write-Host "Using Python: $py"

# --- WavePTX-Relay: the Radio.co stream relay, runs 24/7 in the interactive session ---
$relayArgs = "`"$Root\src\radioco_relay.py`" `"$Root\config\settings.yaml`" $StationId"
$aR = New-ScheduledTaskAction -Execute $py -Argument $relayArgs -WorkingDirectory $Root
$tR = New-ScheduledTaskTrigger -AtLogOn -User $User
$pR = New-ScheduledTaskPrincipal -UserId $User -RunLevel Highest -LogonType Interactive
$sR = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
        -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
        -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName "WavePTX-Relay" -Action $aR -Trigger $tR `
        -Principal $pR -Settings $sR -Force | Out-Null
Write-Host "Registered task: WavePTX-Relay (Radio.co relay, auto-restart)"

# --- Retire the old local-file engine so it doesn't compete for VB-Cable ---
Stop-ScheduledTask    -TaskName "WavePTX-Engine" -ErrorAction SilentlyContinue
Disable-ScheduledTask -TaskName "WavePTX-Engine" -ErrorAction SilentlyContinue | Out-Null
Write-Host "Disabled task: WavePTX-Engine (old local-file scheduler)"

Write-Host "WavePTX-Watchdog left in place — it now monitors the relay's heartbeat."

Write-Host "`n=== RELAY SERVICE SET UP ===" -ForegroundColor Green
Write-Host "Start it now:   Start-ScheduledTask -TaskName WavePTX-Relay"
Write-Host "Verify:         Get-Process python; Get-Content C:\wave-poc\logs\broadcasts.log -Tail 5"
Write-Host "Reboot test:    Restart-Computer -Force   (then re-check after it comes back)"
