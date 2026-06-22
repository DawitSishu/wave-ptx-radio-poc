"""
Radio.co STREAM RELAY (Path B) — Radio.co as the live source of truth.

While the station is On Air, this pipes its live broadcast to the output device
(VB-Cable -> WAVE in Phase B; just VB-Cable in Phase A). It only relays while a
*prompt* is playing (when relay_match is set), so music/silence is ignored.

Audio path (WDM-KS / VB-Cable safe):
  - ffmpeg decodes the live stream to raw PCM
  - a reader thread fills a small buffer from ffmpeg
  - a sounddevice CALLBACK output stream drains the buffer to the device
    (callback mode is required — VB-Cable's WDM-KS has no blocking API)
  - a poller thread hits the PUBLIC now-playing API (no key) to gate relaying

Requires: ffmpeg on PATH, station On Air.
Run:  python src/radioco_relay.py config/settings.yaml <station_id>
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
SR = 44100              # PCM sample rate out of ffmpeg
CH = 2                  # stereo
BPF = CH * 2            # bytes per frame (int16 stereo)
MAXBUF = SR * BPF * 4   # ~4s buffer cap

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("relay")


def load(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def stream_url(station_id):
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
    """No relay_match -> relay whatever the (online) station plays. Else match title."""
    match = (settings.get("radioco") or {}).get("relay_match")
    if not match:
        return True
    return bool(title) and match.lower() in title.lower()


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

    state = {"relay": False, "buf": bytearray()}
    lock = threading.Lock()

    def reader(proc):
        while True:
            d = proc.stdout.read(4096)
            if not d:
                break
            with lock:
                state["buf"].extend(d)
                if len(state["buf"]) > MAXBUF:
                    del state["buf"][:len(state["buf"]) - MAXBUF]

    def callback(outdata, frames, time_info, status):  # noqa: ARG001
        need = frames * BPF
        with lock:
            if state["relay"] and len(state["buf"]) >= need:
                outdata[:] = bytes(state["buf"][:need])
                del state["buf"][:need]
            else:
                outdata[:] = b"\x00" * need
                if not state["relay"]:
                    state["buf"].clear()

    out = sd.RawOutputStream(samplerate=SR, channels=CH, dtype="int16",
                             device=device, callback=callback)
    out.start()

    ff = None
    relaying = False
    try:
        while True:
            if not npoll.online:
                if ff:
                    ff.kill(); ff = None
                with lock:
                    state["relay"] = False
                relaying = False
                log.info("station Off Air - waiting for it to go live...")
                time.sleep(3)
                continue

            if ff is None:
                ff = subprocess.Popen(
                    ["ffmpeg", "-loglevel", "quiet", "-i", url,
                     "-f", "s16le", "-acodec", "pcm_s16le",
                     "-ac", str(CH), "-ar", str(SR), "-"],
                    stdout=subprocess.PIPE)
                threading.Thread(target=reader, args=(ff,), daemon=True).start()
                log.info("ffmpeg decoding the live stream")

            relay = should_relay(npoll.title, s)
            with lock:
                state["relay"] = relay
            if relay and not relaying:
                log.info("RELAYING prompt -> radios: %s", npoll.title or "(on air)")
                relaying = True
            elif not relay and relaying:
                log.info("stopped relaying (now playing: %s)", npoll.title)
                relaying = False
            time.sleep(1)
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
