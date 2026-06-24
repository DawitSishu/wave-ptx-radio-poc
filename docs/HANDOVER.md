# Handover — operating the WAVE PTX radio system

## What it does

Broadcasts a restaurant's operational voice prompts from **Radio.co** to **Motorola
TLK 25 radios** via **WAVE PTX**, automatically.

```
Radio.co  -->  VM relay  -->  VB-Cable  -->  WAVE PTX  -->  talk group  -->  radios
(source of    (mirrors the   (audio wire   (auto PTT      (all or
 truth)        broadcast,     into WAVE)     when a         selected
               prompts only)                 prompt airs)   locations)
```

- **Radio.co** = source of truth (prompts + schedule + timezone live there).
- **VM relay** (`WavePTX-Relay`) = pulls Radio.co's live stream, airs only the
  prompts (filtered by `relay_match`), into VB-Cable.
- **WAVE PTX** = keys push-to-talk on the talk group so the audio reaches the radios
  (Phase B — needs the WAVE Dispatch license).

## The VM

Everything lives in **`C:\wave-poc`**. Two scheduled tasks run it:

| Task | What it does |
|---|---|
| **WavePTX-Relay** | the relay — auto-starts at logon, auto-restarts on crash |
| **WavePTX-Watchdog** | every 3 min; Slack alert if the relay's heartbeat goes stale |

The VM auto-logs-in (`waveadmin`) and never sleeps, so the relay runs 24/7 even with
nobody connected.

## Operate it

```powershell
# Is it running?
Get-ScheduledTask WavePTX-* | Get-ScheduledTaskInfo | Select TaskName, LastRunTime, LastTaskResult
Get-Process python | Select Id, ProcessName

# Watch what it's airing, live:
Get-Content C:\wave-poc\logs\broadcasts.log -Wait -Tail 10

# Restart it (e.g. after a config change):
Stop-ScheduledTask WavePTX-Relay; Start-Sleep 3; Start-ScheduledTask WavePTX-Relay

# Health check on demand:
python C:\wave-poc\src\watchdog.py C:\wave-poc\config\settings.yaml
```

`LastTaskResult 267009` = running. Logs: `C:\wave-poc\logs\broadcasts.log`.

## Config — `config/settings.yaml`

| Field | Meaning |
|---|---|
| `output_device` | the audio device the relay plays into (VB-Cable for production) |
| `radioco.station_id` | the Radio.co station |
| `radioco.relay_match` | only air prompts whose title contains this (`SERGEANT`) |
| `alerts.slack_webhook` | where failure/recovery alerts go |
| `wave.mode` | `off` (Phase A) / `sim` (test) / `dispatch` (live transmit) |

After editing settings, **restart the relay** (it reads config at startup).

## Monitoring

The relay writes a heartbeat every loop; the watchdog alerts to Slack if it goes
stale (relay stopped/crashed), then again at most hourly, with a "recovered" note
when it's back. A *crash* auto-restarts; only a *manual stop* leaves it down.

## Changing prompts / schedule / timezone

All done in **Radio.co** — no code changes. See `docs/RADIOCO-SCHEDULING.md`.

## Phase B (live transmit) — what's left

Gated on the **WAVE Dispatch license**. To finish: log into Dispatch on the VM, set
**CABLE Output** as its mic, fill `wave.selectors` from the live console, set
`wave.mode: dispatch`, and validate a prompt on a real radio. See
`docs/PHASE-B-PLAN.md`. The control logic is already built + validated in `sim` mode.

## Scaling to 10 locations / 40 radios

The system already broadcasts to a **talk group**, so it scales by talk-group
mapping, not by code:
- **One group for all 10 locations** → a prompt reaches every radio at once.
- **Per-location groups** → target one restaurant (set `wave.talkgroup`, or run a
  relay instance per group).
The relay + WAVE handle the fan-out; adding radios just means joining them to the
right talk group in WAVE.
