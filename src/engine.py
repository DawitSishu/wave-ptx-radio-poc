"""
Broadcast engine: reads the data-driven schedule and transmits each reminder at
its scheduled time. Adding or removing a reminder is a schedule.yaml edit, never
a code change. The schedule is re-read every loop, so edits take effect live.
"""
import logging
import os
import sys
import time
from datetime import datetime

import yaml

from notify import send_alert
from ptt import get_adapter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("engine")

_DAY = {0: "mon", 1: "tue", 2: "wed", 3: "thu", 4: "fri", 5: "sat", 6: "sun"}


def load_yaml(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def due_now(item, now):
    if item["time"] != now.strftime("%H:%M"):
        return False
    days = item.get("days", "all")
    if days == "all":
        return True
    return _DAY[now.weekday()] in [d.lower() for d in days]


def run(settings_path):
    settings = load_yaml(settings_path)
    adapter = get_adapter(settings)
    last_fired = set()  # guard against double-firing inside the same minute

    log.info("Engine started (adapter=%s)", settings.get("ptt_adapter"))
    while True:
        now = datetime.now()
        minute_key = now.strftime("%Y-%m-%d %H:%M")

        try:
            schedule = load_yaml(settings["schedule_file"])  # re-read -> live edits
        except Exception as e:  # noqa: BLE001
            send_alert(settings, "Schedule unreadable", str(e))
            time.sleep(20)
            continue

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

        if len(last_fired) > 500:  # keep the dedupe set bounded
            last_fired = set(list(last_fired)[-200:])
        time.sleep(20)


if __name__ == "__main__":
    cfg = sys.argv[1] if len(sys.argv) > 1 else "config/settings.yaml"
    run(cfg)
