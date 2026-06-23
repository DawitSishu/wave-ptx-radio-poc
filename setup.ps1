<#
  One-time setup for the WAVE PTX radio relay on a Windows VM.

    - autologon           (so an interactive audio session exists after reboot)
    - power: never sleep
    - production config   (relay -> VB-Cable, relay_match, monitoring)
    - WavePTX-Relay       : Radio.co relay, auto-starts at logon, auto-restarts
    - WavePTX-Watchdog    : every 3 min; Slack alert if the relay heartbeat goes stale

  Prereqs already on the box: Python 3.12, VB-Cable, ffmpeg, the repo at C:\wave-poc.

  Run once, as administrator:
    powershell -ExecutionPolicy Bypass -File setup.ps1 -Password 'VM_PASSWORD' -StationId s62f446ec2

  NOTE: this overwrites config\settings.yaml, so set the Slack webhook AFTER running it.
#>
param(
  [Parameter(Mandatory = $true)][string]$Password,
  [string]$StationId = "s62f446ec2",
  [string]$User = "waveadmin",
  [string]$Root = "C:\wave-poc"
)
$ErrorActionPreference = "Stop"

$py = "C:\Program Files\Python312\python.exe"
if (-not (Test-Path $py)) { $py = (Get-Command python).Source }
Write-Host "Using Python: $py"

# --- production settings.yaml (forward slashes: YAML treats backslash as an escape) ---
$RootY = $Root -replace '\\', '/'
$settings = @"
output_device: "Speakers (VB-Audio Point)"
log_file: "$RootY/logs/broadcasts.log"
heartbeat_file: "$RootY/logs/heartbeat.txt"
heartbeat_minutes: 15
watchdog_max_age_seconds: 180
alerts:
  slack_webhook: ""          # set this after running setup (see README)
radioco:
  station_id: "$StationId"
  relay_match: "SERGEANT"    # relay only the operational prompts, ignore other audio
wave:
  mode: "off"                # off | sim | dispatch
  talkgroup: "all-restaurants"
  grant_wait: 1.0
"@
$settings | Set-Content -Encoding ascii "$Root\config\settings.yaml"
Write-Host "Wrote production config\settings.yaml"

# --- autologon ---
$wl = "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon"
Set-ItemProperty $wl "AutoAdminLogon"    "1"
Set-ItemProperty $wl "DefaultUserName"   $User
Set-ItemProperty $wl "DefaultPassword"   $Password
Set-ItemProperty $wl "DefaultDomainName" $env:COMPUTERNAME
Write-Host "Autologon enabled for $User"

# --- power: never sleep ---
powercfg /change standby-timeout-ac 0 | Out-Null
powercfg /change monitor-timeout-ac 0 | Out-Null
Write-Host "Power: never sleep"

$pr = New-ScheduledTaskPrincipal -UserId $User -RunLevel Highest -LogonType Interactive

# --- WavePTX-Relay (the Radio.co relay, 24/7) ---
$relayArgs = "`"$Root\src\radioco_relay.py`" `"$Root\config\settings.yaml`" $StationId"
$aR = New-ScheduledTaskAction -Execute $py -Argument $relayArgs -WorkingDirectory $Root
$tR = New-ScheduledTaskTrigger -AtLogOn -User $User
$sR = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
        -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
        -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName "WavePTX-Relay" -Action $aR -Trigger $tR `
        -Principal $pr -Settings $sR -Force | Out-Null
Write-Host "Registered task: WavePTX-Relay"

# --- WavePTX-Watchdog (every 3 min) ---
$wdArgs = "`"$Root\src\watchdog.py`" `"$Root\config\settings.yaml`""
$aW = New-ScheduledTaskAction -Execute $py -Argument $wdArgs -WorkingDirectory $Root
$tW = New-ScheduledTaskTrigger -Once -At (Get-Date) `
        -RepetitionInterval (New-TimeSpan -Minutes 3) -RepetitionDuration (New-TimeSpan -Days 3650)
Register-ScheduledTask -TaskName "WavePTX-Watchdog" -Action $aW -Trigger $tW `
        -Principal $pr -Settings (New-ScheduledTaskSettingsSet) -Force | Out-Null
Write-Host "Registered task: WavePTX-Watchdog"

Write-Host "`n=== SETUP COMPLETE ===" -ForegroundColor Green
Write-Host "1) Set the Slack webhook in config\settings.yaml"
Write-Host "2) Reboot to verify:  Restart-Computer -Force"
Write-Host "3) After reboot:  Get-ScheduledTask WavePTX-* | Get-ScheduledTaskInfo"
