"""
Radio.co STREAM RELAY (Path B) — Radio.co as the live source of truth.

While the station is On Air, this pipes its live broadcast to the output device
(VB-Cable -> WAVE in Phase B; just VB-Cable in Phase A). It only relays while a
*prompt* is playing, so any music/silence between prompts is ignored.

How it works:
  - ffmpeg decodes the live stream to raw PCM (handles the network + mp3 decode)
  - a background thread polls the PUBLIC now-playing API (no API key needed)
  - audio is written to the device only while the current track passes the filter;
    silence is written otherwise so the device stays fed

Requires: ffmpeg on PATH, and the station On Air.
Run:  python src/radioco_relay.py config/settings.yaml
"""
import logging
import subprocess
import sys
import threading
import time

import requests
import sounddevice as sd
import yaml

PUBLIC = "https://public.radio.co"
SR = 44100          # PCM sample rate out of ffmpeg
CH = 2              # stereo
CHUNK = 1024        # frames per read

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("relay")


def load(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def stream_url(station_id):
    """Resolve the listen URL from the public status, else the standard form."""
    try:
        data = requests.get(f"{PUBLIC}/stations/{station_id}/status",
                            timeout=10).json() or {}
        host = data.get("streaming_hostname") or "streaming.radio.co"
        for o in (data.get("outputs") or []):
            if o.get("name"):
                return f"https://{host}/{station_id}/{o['name']}"
    except Exception as e:  # noqa: BLE001
        log.warning("status lookup failed: %s", e)
    return f"https://streaming.radio.co/{station_id}/listen"


class NowPlaying(threading.Thread):
    """Polls the public now-playing + status APIs (no key)."""

    def __init__(self, station_id, interval=4):
        super().__init__(daemon=True)
        self.station_id = station_id
        self.interval = interval
        self.title = None
        self.online = False
        self._stop = False

    def run(self):
        cur_url = f"{PUBLIC}/api/v2/{self.station_id}/track/current"
        st_url = f"{PUBLIC}/stations/{self.station_id}/status"
        while not self._stop:
            try:
                cur = requests.get(cur_url, timeout=10).json() or {}
                st = requests.get(st_url, timeout=10).json() or {}
                self.title = (cur.get("title")
                              or (cur.get("current_track") or {}).get("title")
                              or (st.get("current_track") or {}).get("title"))
                self.online = st.get("status") == "online"
            except Exception as e:  # noqa: BLE001
                log.warning("now-playing poll failed: %s", e)
            time.sleep(self.interval)

    def stop(self):
        self._stop = True


def should_relay(title, settings):
    """Relay everything by default; if relay_match is set, only matching titles."""
    if not title:
        return False
    match = (settings.get("radioco") or {}).get("relay_match")
    return True if not match else match.lower() in title.lower()


def run(settings_path, station_id=None):
    s = load(settings_path)
    sid = station_id or (s.get("radioco") or {}).get("station_id")
    device = s.get("output_device")
    if not sid:
        log.error("station_id not set (pass it as the 2nd argument)"); return

    url = stream_url(sid)
    log.info("Relay starting. station=%s device=%s", sid, device)
    log.info("Stream URL: %s", url)

    npoll = NowPlaying(sid)
    npoll.start()

    out = sd.RawOutputStream(samplerate=SR, channels=CH, dtype="int16",
                             device=device)
    out.start()
    ff = None
    relaying = False
    silence = b"\x00" * (CHUNK * CH * 2)
    try:
        while True:
            if not npoll.online:
                if ff:
                    ff.kill(); ff = None
                log.info("station Off Air - waiting for it to go live...")
                time.sleep(3)
                continue

            if ff is None:
                ff = subprocess.Popen(
                    ["ffmpeg", "-loglevel", "quiet", "-i", url,
                     "-f", "s16le", "-acodec", "pcm_s16le",
                     "-ac", str(CH), "-ar", str(SR), "-"],
                    stdout=subprocess.PIPE)
                log.info("ffmpeg decoding the live stream")

            data = ff.stdout.read(CHUNK * CH * 2)
            if not data:
                ff.kill(); ff = None; time.sleep(1); continue

            relay = should_relay(npoll.title, s)
            if relay and not relaying:
                log.info("RELAYING prompt -> radios: %s", npoll.title)
                relaying = True
            elif not relay and relaying:
                log.info("stopped relaying (now playing: %s)", npoll.title)
                relaying = False

            out.write(data if relay else silence)
    except KeyboardInterrupt:
        pass
    finally:
        if ff:
            ff.kill()
        out.stop(); out.close(); npoll.stop()


if __name__ == "__main__":
    cfg = sys.argv[1] if len(sys.argv) > 1 else "config/settings.yaml"
    sid = sys.argv[2] if len(sys.argv) > 2 else None
    run(cfg, sid)
