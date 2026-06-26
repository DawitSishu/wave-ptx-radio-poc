"""
Broadcast engine (custom system) - plays scheduled prompts, no Radio.co.

Reads config/schedule.yaml (managed by the web dashboard) and at each scheduled
time plays that prompt from the audio/ folder to the output device (VB-Cable),
keying WAVE push-to-talk around it. Writes a heartbeat so the watchdog can monitor it.

This is the "custom" broadcaster: dashboard -> schedule.yaml -> engine -> VB-Cable
-> WAVE -> radios.  (The Radio.co relay is the alternative source; only one should
drive VB-Cable at a time.)

    python src/engine.py config/settings.yaml
"""
import logging
import os
import sys
import time
from datetime import datetime

import numpy as np
import sounddevice as sd
import soundfile as sf
import yaml

from notify import send_alert
from wave_dispatch import get_controller

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
log = logging.getLogger("engine")

_DAY = {0: "mon", 1: "tue", 2: "wed", 3: "thu", 4: "fri", 5: "sat", 6: "sun"}
_tz_warned = set()


def load_yaml(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _setup_file_log(path):
    if not path:
        return
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    from logging.handlers import RotatingFileHandler
    fh = RotatingFileHandler(path, maxBytes=5_000_000, backupCount=3, encoding="utf-8")
    fh.setFormatter(logging.Formatter(LOG_FORMAT))
    logging.getLogger().addHandler(fh)


def _touch(path):
    if not path:
        return
    try:
        folder = os.path.dirname(path)
        if folder:
            os.makedirs(folder, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write("engine alive")
    except Exception:  # noqa: BLE001
        pass


def now_in_tz(tzname):
    if tzname and ZoneInfo:
        try:
            return datetime.now(ZoneInfo(tzname))
        except Exception:  # noqa: BLE001
            if tzname not in _tz_warned:
                log.warning("Timezone %r unavailable (need 'tzdata'?) - using system local",
                            tzname)
                _tz_warned.add(tzname)
    return datetime.now()


def due_now(item, now):
    if item.get("time") != now.strftime("%H:%M"):
        return False
    days = item.get("days", "all")
    if days == "all":
        return True
    return _DAY[now.weekday()] in [d.lower() for d in days]


def play(path, device, lead):
    data, sr = sf.read(path, dtype="float32")
    if lead:
        pad = np.zeros((int(sr * lead),) + data.shape[1:], dtype="float32")
        data = np.concatenate([pad, data])
    sd.play(data, sr, device=device)
    sd.wait()


def run(settings_path):
    s = load_yaml(settings_path)
    _setup_file_log(s.get("log_file"))
    device = s.get("output_device")
    lead = s.get("ptt_lead_silence", 0.5)
    hb = s.get("heartbeat_file") or os.path.join(
        os.path.dirname(s.get("log_file", "")) or ".", "heartbeat.txt")
    hb_interval = s.get("heartbeat_minutes", 15) * 60
    last_hb = 0.0
    last_fired = set()

    wave = get_controller(s)
    wave.start()
    log.info("Engine started (schedule-driven, device=%s)", device)

    while True:
        wall = time.time()
        _touch(hb)
        try:
            sched = load_yaml(s["schedule_file"])     # re-read -> live dashboard edits
        except Exception as e:  # noqa: BLE001
            send_alert(s, "Schedule unreadable", str(e))
            time.sleep(20)
            continue

        now = now_in_tz(sched.get("timezone"))
        minute_key = now.strftime("%Y-%m-%d %H:%M")
        for item in sched.get("broadcasts", []):
            fire_id = "%s|%s" % (minute_key, item.get("label", item.get("audio")))
            if fire_id in last_fired or not due_now(item, now):
                continue
            last_fired.add(fire_id)

            audio = os.path.join(s["audio_dir"], item["audio"])
            if not os.path.exists(audio):
                send_alert(s, "Audio file missing",
                           "%s: %s not found - prompt MISSED" % (item.get("label"), audio))
                continue
            tg = item.get("talkgroup", "all-restaurants")
            try:
                wave.key(tg)
                play(audio, device, lead)
                wave.unkey()
                log.info("OK  %s -> %s", item.get("label", item["audio"]), tg)
            except Exception as e:  # noqa: BLE001
                send_alert(s, "Broadcast error", "%s: %s" % (item.get("label"), e))

        if wall - last_hb >= hb_interval:
            log.info("heartbeat - alive, %d prompts scheduled",
                     len(sched.get("broadcasts", [])))
            last_hb = wall
        if len(last_fired) > 500:
            last_fired = set(list(last_fired)[-200:])
        time.sleep(20)


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "config/settings.yaml")
