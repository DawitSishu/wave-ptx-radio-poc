# WAVE PTX Automated Radio Reminders — POC

Scheduled voice reminders that auto-transmit to Motorola TLK 25 radios via
WAVE PTX, with monitoring and failure alerts.

## How it works

```
config/schedule.yaml (data) -> engine.py -> audio out (VB-Cable) -> WAVE PTX -> radios
                                     \-> alerts on failure / missed message
```

## Why you never write code to add a reminder

Reminders live in `config/schedule.yaml` as plain data (audio file + time +
talk group). To add one: drop the mp3 in `audio/`, add one line to the
schedule. Done — no code change. The code is a fixed "engine" that plays
whatever the schedule says, so it scales from 25 prompts to hundreds without
edits. Later the same schedule can be driven from a spreadsheet or a web UI.

## Two phases

- **Phase A (no Dispatch license needed):** VM + audio routing + engine +
  scheduling + monitoring, validated with the `loopback` adapter. See
  `docs/VM-SETUP.md`.
- **Phase B (Dispatch license live):** the `dispatch` adapter drives the
  WAVE PTX Dispatch console for real transmits; validate on a real TLK 25.

## Run

```
pip install -r requirements.txt
cp config/settings.example.yaml config/settings.yaml   # then edit it
python src/engine.py config/settings.yaml
```
