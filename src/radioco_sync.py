"""
Radio.co sync — makes Radio.co the upstream SOURCE OF TRUTH.

Pulls audio prompts (and schedule) from the station's Radio.co account down to the
VM, so anything loaded/scheduled in Radio.co is automatically consumed by the
engine. The engine still executes locally for precise timing + reliability.

Build status:
  - check()        : reachability via the PUBLIC API (no key needed)  -> WORKS NOW
  - sync_media()   : list + download Media Library tracks (Studio API) -> wired once
                     we confirm the Studio API endpoints + key
  - sync_schedule(): read scheduled events -> schedule.yaml (Studio API) -> same

Usage:
    python src/radioco_sync.py check <station_id>
    python src/radioco_sync.py sync  config/settings.yaml      (once endpoints wired)
"""
import sys
import os

import requests
import yaml

PUBLIC = "https://public.radio.co"


def load_settings(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def check(station_id):
    """Prove we can reach the Radio.co account (public API, no key required)."""
    if not station_id:
        print("Need a station_id (it's in your Studio dashboard URL: "
              "studio.radio.co/stations/<ID>/dashboard).")
        return False
    url = f"{PUBLIC}/stations/{station_id}/status"
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    data = r.json()
    print("Radio.co REACHABLE from this VM.")
    print("  station :", data.get("name") or data.get("station", {}).get("name", "?"))
    print("  status  :", data.get("status", "?"))
    print("  raw keys:", list(data.keys()))
    return True


# --- filled in once the Studio API reference + API key are confirmed ---
def sync_media(settings):
    """List Media Library tracks and download any new ones into audio/."""
    raise NotImplementedError("Wire to the Studio API media endpoints + key.")


def sync_schedule(settings):
    """Read Radio.co scheduled events and write schedule.yaml."""
    raise NotImplementedError("Wire to the Studio API schedule endpoints + key.")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "check":
        sid = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("RADIOCO_STATION_ID", "")
        sys.exit(0 if check(sid) else 1)
    elif cmd == "sync":
        cfg = sys.argv[2] if len(sys.argv) > 2 else "config/settings.yaml"
        s = load_settings(cfg)
        sync_media(s)
        sync_schedule(s)
    else:
        print("Usage: radioco_sync.py [check <station_id> | sync <settings.yaml>]")
