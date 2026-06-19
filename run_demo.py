"""
Phase A demo runner: schedules a TEST reminder 2 minutes out and starts the
engine, so you can watch it fire on time and hear the audio. No radio needed.

    python run_demo.py

Writes config/schedule.yaml + config/settings.yaml (tuned to play to the
default/audible device), then runs the engine. Ctrl+C to stop.
"""
import os
import sys
from datetime import datetime, timedelta

try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo("America/Chicago")
except Exception:  # noqa: BLE001 - missing tzdata -> fall back to system local
    TZ = None

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))

audio_dir = os.path.join(ROOT, "audio").replace("\\", "/")
schedule_file = os.path.join(ROOT, "config", "schedule.yaml").replace("\\", "/")
settings_file = os.path.join(ROOT, "config", "settings.yaml")
log_file = os.path.join(ROOT, "logs", "broadcasts.log").replace("\\", "/")

audio_name = sys.argv[1] if len(sys.argv) > 1 else "test-reminder.wav"
now = datetime.now(TZ)
fire = (now + timedelta(minutes=2)).strftime("%H:%M")

schedule = f'''timezone: "America/Chicago"
broadcasts:
  - time: "{fire}"
    days: all
    audio: "{audio_name}"
    talkgroup: "test-group"
    label: "TEST reminder ({audio_name})"
'''

settings = f'''audio_dir: "{audio_dir}"
schedule_file: "{schedule_file}"
output_device: null
ptt_lead_silence: 0.5
ptt_adapter: "loopback"
alerts:
  slack_webhook: ""
log_file: "{log_file}"
'''

with open(schedule_file, "w", encoding="utf-8") as f:
    f.write(schedule)
with open(settings_file, "w", encoding="utf-8") as f:
    f.write(settings)

tzlabel = "America/Chicago" if TZ else "system local time"
print(f"Scheduled TEST reminder for {fire} ({tzlabel}). It's now {now:%H:%M:%S} there.")
print("Engine starting — leave it running, watch for the 'OK' line, and listen...\n")

import engine  # noqa: E402  (path set above)
engine.run(settings_file)
