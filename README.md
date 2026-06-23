# WAVE PTX Automated Radio Reminders

Broadcasts a restaurant's operational voice prompts from **Radio.co** out to
**Motorola TLK 25 radios** via **WAVE PTX**, automatically and on schedule.

## How it works

```
Radio.co  -->  VM relay  -->  VB-Cable  -->  WAVE PTX  -->  talk group  -->  TLK 25 radios
(source of    (re-airs the   (audio wire   (auto PTT      (all or         (staff hear it
 truth:        live          into WAVE)     when a         selected         across 10
 prompts +     broadcast)                   prompt airs)   locations)       locations)
 schedule)
```

- **Radio.co is the source of truth.** Staff upload prompts and schedule them there.
  When the station is On Air, Radio.co broadcasts them as a live stream.
- The **relay** (`src/radioco_relay.py`) pulls that live broadcast on the VM and
  feeds it into **VB-Cable**, only while an actual prompt is airing
  (`radioco.relay_match`). No API key needed — it uses the public stream + the
  public now-playing API.
- **WAVE PTX** (`src/wave_dispatch.py`) keys push-to-talk on the talk group while a
  prompt airs, so the audio goes out to every radio in the group.

## Phases

- **Phase A (done):** Radio.co -> VM relay, running 24/7 (auto-start, auto-restart,
  reboot-tested), with monitoring + Slack alerts.
- **Phase B (in progress, gated on the WAVE license):** the live transmit to the
  radios. The control logic is built and validated in `sim` mode; the real
  `dispatch` mode needs the WAVE console's selectors (see `wave.selectors` in the
  config). Plan: `docs/PHASE-B-PLAN.md`.

## Layout

```
src/radioco_relay.py   the relay (Radio.co live stream -> VB-Cable, + WAVE PTT trigger)
src/wave_dispatch.py   WAVE PTX transmit control: off | sim | dispatch
src/watchdog.py        alerts to Slack if the relay heartbeat goes stale
src/notify.py          Slack / email alert helper
config/settings.example.yaml   copy to settings.yaml and fill in
setup.ps1              one-time VM setup (autologon, power, config, the two tasks)
docs/PHASE-B-PLAN.md   the remaining Phase B work
```

## Run / operate

The VM runs two scheduled tasks: **WavePTX-Relay** (the relay) and **WavePTX-Watchdog**
(monitoring). To stand it up on a fresh box (Python 3.12 + VB-Cable + ffmpeg + this
repo at `C:\wave-poc` already installed):

```powershell
powershell -ExecutionPolicy Bypass -File setup.ps1 -Password 'VM_PASSWORD' -StationId s62f446ec2
# then set the Slack webhook in config\settings.yaml and reboot
```

Test the WAVE transmit flow without a license (simulation):

```powershell
$env:WAVE_MODE="sim"
python src\radioco_relay.py config\settings.yaml <station_id> default
```
