"""
Watchdog: alerts (Slack/email) if the relay's heartbeat goes stale - i.e. the relay
crashed, hung, or was stopped. Run on a short schedule (Task Scheduler ~every 3 min).

To avoid alert spam it tracks state in a small file and only:
  - alerts when the relay FIRST goes down, then at most once per alert_cooldown_seconds,
  - sends one "recovered" note when the heartbeat is fresh again.

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


def _state_path(settings):
    base = os.path.dirname(settings.get("log_file", "")) or "."
    return os.path.join(base, "watchdog_state.txt")


def _read_state(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            status, last = f.read().strip().split(",")
            return status, float(last)
    except Exception:  # noqa: BLE001
        return "ok", 0.0


def _write_state(path, status, last_alert):
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write("%s,%f" % (status, last_alert))
    except Exception:  # noqa: BLE001
        pass


def main(settings_path):
    with open(settings_path, "r", encoding="utf-8") as f:
        settings = yaml.safe_load(f)

    hb = _heartbeat_path(settings)
    max_age = settings.get("watchdog_max_age_seconds", 180)
    cooldown = settings.get("alert_cooldown_seconds", 3600)   # re-alert at most hourly
    state_file = _state_path(settings)
    prev_status, last_alert = _read_state(state_file)
    now = time.time()

    exists = os.path.exists(hb)
    age = int(now - os.path.getmtime(hb)) if exists else -1
    down = (not exists) or (age > max_age)

    if down:
        detail = ("no heartbeat file" if not exists
                  else "heartbeat %ds old (limit %ds)" % (age, max_age))
        if prev_status != "down" or (now - last_alert) >= cooldown:
            send_alert(settings, "Relay DOWN",
                       "The radio relay appears stopped (%s). Reminders are NOT "
                       "going out. It auto-restarts on crash; if this persists, "
                       "check the VM." % detail)
            last_alert = now
            print("ALERT sent: %s" % detail)
        else:
            print("DOWN (alert suppressed by cooldown): %s" % detail)
        _write_state(state_file, "down", last_alert)
        return 1

    if prev_status == "down":
        send_alert(settings, "Relay RECOVERED",
                   "The radio relay is back - heartbeat is fresh again.")
        print("RECOVERED")
    _write_state(state_file, "ok", last_alert)
    print("OK - heartbeat %ds old (limit %ds)" % (age, max_age))
    return 0


if __name__ == "__main__":
    cfg = sys.argv[1] if len(sys.argv) > 1 else "config/settings.yaml"
    sys.exit(main(cfg))
