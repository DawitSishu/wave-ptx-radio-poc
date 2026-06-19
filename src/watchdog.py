"""
Watchdog: alerts (Slack/email) if the engine's heartbeat goes stale — i.e. the
engine crashed, hung, or never started. This is the "tell us if it stops" piece.

The engine touches a heartbeat file every loop (~20s). This script checks that
file's age and alerts if it's older than watchdog_max_age_seconds. Run it on a
short schedule (e.g. Windows Task Scheduler every 2-3 min) so a dead engine is
caught quickly and reported.

    python src/watchdog.py config/settings.yaml
"""
import os
import sys
import time

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from notify import send_alert  # noqa: E402


def _heartbeat_path(settings):
    hb = settings.get("heartbeat_file")
    if hb:
        return hb
    base = os.path.dirname(settings.get("log_file", "")) or "."
    return os.path.join(base, "heartbeat.txt")


def main(settings_path):
    with open(settings_path, "r", encoding="utf-8") as f:
        settings = yaml.safe_load(f)

    hb = _heartbeat_path(settings)
    max_age = settings.get("watchdog_max_age_seconds", 180)

    if not os.path.exists(hb):
        send_alert(settings, "Engine DOWN",
                   f"No heartbeat file at {hb} — the broadcast engine may not be "
                   f"running. Check the VM.")
        print(f"ALERT: no heartbeat file at {hb}")
        return 1

    age = int(time.time() - os.path.getmtime(hb))
    if age > max_age:
        send_alert(settings, "Engine DOWN",
                   f"Heartbeat is {age}s old (limit {max_age}s) — the broadcast "
                   f"engine appears stopped. Scheduled reminders are NOT firing.")
        print(f"ALERT: heartbeat {age}s old (> {max_age}s)")
        return 1

    print(f"OK — heartbeat {age}s old (limit {max_age}s)")
    return 0


if __name__ == "__main__":
    cfg = sys.argv[1] if len(sys.argv) > 1 else "config/settings.yaml"
    sys.exit(main(cfg))
