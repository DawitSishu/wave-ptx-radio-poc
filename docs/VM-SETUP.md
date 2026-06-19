# Phase A — VM setup runbook (no Dispatch license needed)

Goal: a Windows VM that boots, logs in, routes audio into WAVE PTX, and runs the
broadcast engine 24/7.

## 1. Base VM
- Windows Server 2022 or Windows 11, B2s or larger.
- RDP enabled; firewall locked to known IPs.

## 2. Autologon (so audio + engine survive reboots)
- `netplwiz` (or Sysinternals Autologon): auto-log-in the service account.
  Windows audio needs an interactive session — there is no truly headless audio.
- Power plan: High performance, never sleep, never turn off the display.

## 3. Virtual audio cable
- Install VB-Audio Virtual Cable.
- Set **CABLE Input** as the default playback device.
- Phase B: set **CABLE Output** as WAVE PTX Dispatch's microphone.

## 4. Runtime
- Install Python 3.11+.
- `pip install -r requirements.txt`
- `python -m sounddevice` to get the exact output device name; put it in
  `settings.yaml` as `output_device`.

## 5. Loopback test (proves Phase A)
- `ptt_adapter: loopback` in settings.yaml.
- `python src/engine.py config/settings.yaml`
- Add a test entry to schedule.yaml a couple of minutes out; confirm it plays
  cleanly through CABLE Input at the right time and logs `OK`.

## 6. Run on boot / keep alive
- NSSM or Task Scheduler (at logon) to keep `engine.py` running with
  auto-restart. The heartbeat alerts if it ever stops.

## Phase B (once the Dispatch license registers)
- Log into WAVE PTX Dispatch in a browser on the VM; join the test talk group.
- Set CABLE Output as Dispatch's mic input.
- Fill in the selectors in `DispatchAdapter` (src/ptt.py), set
  `ptt_adapter: dispatch`, and validate a live transmit to a TLK 25.
