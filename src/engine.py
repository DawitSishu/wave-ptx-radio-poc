"""
Broadcast engine: reads the data-driven schedule and transmits each reminder at
its scheduled time. Adding or removing a reminder is a schedule.yaml edit, never
a code change. The schedule is re-read every loop, so edits take effect live.

Scheduling is timezone-aware: the `timezone:` field in schedule.yaml decides what
"08:00" means (e.g. America/Chicago), independent of the VM's clock (Azure = UTC).
A heartbeat file is touched every loop so the watchdog can detect a dead engine.
"""
import logging
import os
import sys
import time
from datetime import datetime

import yaml

from notify import send_alert
from ptt import get_adapter

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - Python < 3.9
    ZoneInfo = None

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
log = logging.getLogger("engine")

_DAY = {0: "mon", 1: "tue", 2: "wed", 3: "thu", 4: "fri", 5: "sat", 6: "sun"}
_tz_warned = set()


def load_yaml(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def now_in_tz(tzname):
    """Current time in the schedule's timezone, falling back to system local."""
    if tzname and ZoneInfo:
        try:
            return datetime.now(ZoneInfo(tzname))
        except Exception:  # noqa: BLE001 - bad tz name or missing tzdata
            if tzname not in _tz_warned:
                log.warning("Timezone %r unavailable (need 'tzdata'?) — using "
                            "system local time", tzname)
                _tz_warned.add(tzname)
    return datetime.now()


def due_now(item, now):
    if item["time"] != now.strftime("%H:%M"):
        return False
    days = item.get("days", "all")
    if days == "all":
        return True
    return _DAY[now.weekday()] in [d.lower() for d in days]


def _setup_file_log(path):
    if not path:
        return
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    fh = logging.FileHandler(path, encoding="utf-8")
    fh.setFormatter(logging.Formatter(LOG_FORMAT))
    logging.getLogger().addHandler(fh)


def _heartbeat_path(settings):
    hb = settings.get("heartbeat_file")
    if hb:
        return hb
    base = os.path.dirname(settings.get("log_file", "")) or "."
    return os.path.join(base, "heartbeat.txt")


def run(settings_path):
    settings = load_yaml(settings_path)
    _setup_file_log(settings.get("log_file"))
    adapter = get_adapter(settings)

    hb_path = _heartbeat_path(settings)
    hb_interval = settings.get("heartbeat_minutes", 15) * 60
    last_hb_log = 0.0
    last_fired = set()  # guard against double-firing inside the same minute

    log.info("Engine started (adapter=%s)", settings.get("ptt_adapter"))
    while True:
        wall = time.time()

        try:
            schedule = load_yaml(settings["schedule_file"])  # re-read -> live edits
        except Exception as e:  # noqa: BLE001
            send_alert(settings, "Schedule unreadable", str(e))
            time.sleep(20)
            continue

        now = now_in_tz(schedule.get("timezone"))
        minute_key = now.strftime("%Y-%m-%d %H:%M")

        for item in schedule.get("broadcasts", []):
            fire_id = f"{minute_key}|{item['label']}"
            if fire_id in last_fired or not due_now(item, now):
                continue
            last_fired.add(fire_id)

            audio = os.path.join(settings["audio_dir"], item["audio"])
            if not os.path.exists(audio):
                send_alert(settings, "Audio file missing",
                           f"{item['label']}: {audio} not found — broadcast MISSED")
                continue

            try:
                if adapter.transmit(audio, item["talkgroup"]):
                    log.info("OK  %s -> %s", item["label"], item["talkgroup"])
                else:
                    send_alert(settings, "Broadcast failed",
                               f"{item['label']} -> {item['talkgroup']} could not transmit")
            except Exception as e:  # noqa: BLE001
                send_alert(settings, "Broadcast error", f"{item['label']}: {e}")

        # Heartbeat: touch a file every loop so the watchdog can see we're alive,
        # and log an "alive" line every heartbeat_minutes.
        try:
            with open(hb_path, "w", encoding="utf-8") as f:
                f.write(now.isoformat())
        except Exception as e:  # noqa: BLE001
            log.error("Could not write heartbeat %s: %s", hb_path, e)
        if wall - last_hb_log >= hb_interval:
            log.info("heartbeat - alive, %d broadcasts scheduled",
                     len(schedule.get("broadcasts", [])))
            last_hb_log = wall

        if len(last_fired) > 500:  # keep the dedupe set bounded
            last_fired = set(list(last_fired)[-200:])
        time.sleep(20)


if __name__ == "__main__":
    cfg = sys.argv[1] if len(sys.argv) > 1 else "config/settings.yaml"
    run(cfg)
