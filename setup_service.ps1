<#
  Configure the WAVE PTX radio engine to run 24/7 UNATTENDED on this VM.

  It sets up:
    - autologon            (so an interactive audio session exists after reboot;
                            Windows audio cannot run truly headless)
    - power plan           (never sleep / never turn off display)
    - production settings  (plays to the always-present VB-Cable, real schedule,
                            monitoring on)
    - WavePTX-Engine task  (runs the engine at logon; auto-restarts if it dies)
    - WavePTX-Watchdog task(runs every 3 min; alerts if the engine stops)

  Run ONCE, in an ADMINISTRATOR PowerShell:
    powershell -ExecutionPolicy Bypass -File setup_service.ps1 -Password 'YOUR_VM_PASSWORD'
#>
param(
  [Parameter(Mandatory = $true)][string]$Password,
  [string]$User = "waveadmin",
  [string]$Root = "C:\wave-poc"
)

$ErrorActionPreference = "Stop"

$py = "C:\Program Files\Python312\python.exe"
if (-not (Test-Path $py)) { $py = (Get-Command python).Source }
Write-Host "Using Python: $py"

# --- production settings.yaml (plays into the always-present VB-Cable) ---
# YAML double-quoted strings treat "\" as an escape, so paths MUST use "/".
$RootY = $Root -replace '\\', '/'
$settings = @"
audio_dir: "$RootY/audio"
schedule_file: "$RootY/config/schedule.yaml"
output_device: "Speakers (VB-Audio Point)"
ptt_lead_silence: 0.5
ptt_adapter: "loopback"
alerts:
  slack_webhook: ""
log_file: "$RootY/logs/broadcasts.log"
heartbeat_minutes: 15
heartbeat_file: "$RootY/logs/heartbeat.txt"
watchdog_max_age_seconds: 180
"@
$settings | Set-Content -Encoding ascii "$Root\config\settings.yaml"
Write-Host "Wrote production config\settings.yaml (output -> VB-Cable)"

# --- pull the production 8am schedule from the repo ---
$base = "https://raw.githubusercontent.com/DawitSishu/wave-ptx-radio-poc/main"
Invoke-WebRequest "$base/config/schedule.yaml" -OutFile "$Root\config\schedule.yaml" -UseBasicParsing
Write-Host "Pulled production config\schedule.yaml (8am daily)"

# --- autologon so the audio session is present after a reboot ---
$wl = "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon"
Set-ItemProperty $wl "AutoAdminLogon"    "1"
Set-ItemProperty $wl "DefaultUserName"   $User
Set-ItemProperty $wl "DefaultPassword"   $Password
Set-ItemProperty $wl "DefaultDomainName" $env:COMPUTERNAME
Write-Host "Autologon enabled for $User"

# --- power: never sleep / never blank ---
powercfg /change standby-timeout-ac 0 | Out-Null
powercfg /change monitor-timeout-ac 0 | Out-Null
powercfg /change disk-timeout-ac 0    | Out-Null
Write-Host "Power plan: never sleep"

# --- scheduled task: the engine (interactive session, auto-restart) ---
$engineArgs = "`"$Root\src\engine.py`" `"$Root\config\settings.yaml`""
$aE = New-ScheduledTaskAction -Execute $py -Argument $engineArgs -WorkingDirectory $Root
$tE = New-ScheduledTaskTrigger -AtLogOn -User $User
$pE = New-ScheduledTaskPrincipal -UserId $User -RunLevel Highest -LogonType Interactive
$sE = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
        -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
        -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName "WavePTX-Engine" -Action $aE -Trigger $tE `
        -Principal $pE -Settings $sE -Force | Out-Null
Write-Host "Registered task: WavePTX-Engine (runs at logon, auto-restarts)"

# --- scheduled task: watchdog every 3 minutes ---
$wdArgs = "`"$Root\src\watchdog.py`" `"$Root\config\settings.yaml`""
$aW = New-ScheduledTaskAction -Execute $py -Argument $wdArgs -WorkingDirectory $Root
$tW = New-ScheduledTaskTrigger -Once -At (Get-Date) `
        -RepetitionInterval (New-TimeSpan -Minutes 3) -RepetitionDuration (New-TimeSpan -Days 3650)
$pW = New-ScheduledTaskPrincipal -UserId $User -RunLevel Highest -LogonType Interactive
Register-ScheduledTask -TaskName "WavePTX-Watchdog" -Action $aW -Trigger $tW `
        -Principal $pW -Settings (New-ScheduledTaskSettingsSet) -Force | Out-Null
Write-Host "Registered task: WavePTX-Watchdog (every 3 min)"

Write-Host "`n=== SETUP COMPLETE ===" -ForegroundColor Green
Write-Host "Reboot to verify the whole unattended chain:" -ForegroundColor Yellow
Write-Host "    Restart-Computer -Force"
Write-Host "After it reboots, reconnect and run:  Get-ScheduledTask WavePTX-* | Get-ScheduledTaskInfo"
