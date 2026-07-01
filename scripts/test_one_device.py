"""
One-device Phase B test — prove a single prompt goes out through the real WAVE
PTX Dispatch on the VM, without waiting for the scheduler.

Run on the VM over JumpDesktop (NOT RDP — RDP redirects the audio session and
breaks the VB-Cable routing / the interactive session Playwright needs).

  # 0) See exact device names; pick the VB-CABLE *Input* for output_device in settings.
  python scripts/test_one_device.py --list-devices

  # Stage 1 — audio routing only. You hold PTT manually in the one-to-one call.
  #   engine plays -> output_device (CABLE Input) -> Dispatch mic (CABLE Output) -> device
  python scripts/test_one_device.py config/settings.yaml --audio opening.mp3

  # Stage 1b — same, but exercise the key->play->release sequencing with SIMULATED ptt
  #   (real audio into VB-Cable, PTT only logged). Good dry-run before wiring the console.
  WAVE_MODE=sim python scripts/test_one_device.py config/settings.yaml --audio opening.mp3 --ptt

  # Stage 2 — full automation. Playwright logs into Dispatch and drives PTT for real.
  #   Needs wave.mode=dispatch + dispatch_url + creds + selectors.ptt (and .granted) set.
  #   Close any manual Dispatch tab first so the automated session owns the license.
  python scripts/test_one_device.py config/settings.yaml --audio opening.mp3 --ptt
"""
import argparse
import logging
import os
import sys

# make src/ importable whether run from the repo root or elsewhere
_SRC = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
sys.path.insert(0, _SRC)

import yaml  # noqa: E402

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("test1")


def load_yaml(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def main():
    ap = argparse.ArgumentParser(description="One-device Phase B transmit test")
    ap.add_argument("settings", nargs="?", default="config/settings.yaml")
    ap.add_argument("--audio", help="audio filename inside audio_dir (or an absolute path)")
    ap.add_argument("--talkgroup", default=None,
                    help="talkgroup/contact to key; omit for a pre-selected one-to-one call")
    ap.add_argument("--ptt", action="store_true",
                    help="drive WAVE PTT via the configured wave.mode (dispatch/sim)")
    ap.add_argument("--list-devices", action="store_true",
                    help="print audio devices and exit (pick the VB-CABLE Input for output_device)")
    args = ap.parse_args()

    import sounddevice as sd
    if args.list_devices:
        print(sd.query_devices())
        return

    if not args.audio:
        ap.error("--audio is required (unless --list-devices)")

    s = load_yaml(args.settings)
    device = s.get("output_device")
    lead = s.get("ptt_lead_silence", 0.5)

    audio = args.audio if os.path.isabs(args.audio) else os.path.join(s["audio_dir"], args.audio)
    if not os.path.exists(audio):
        log.error("audio not found: %s", audio)
        sys.exit(1)

    from engine import play  # reuse the EXACT playback path the engine uses

    if not args.ptt:
        log.info("STAGE 1: playing %s -> device=%s  (hold PTT manually in Dispatch now)",
                 audio, device)
        play(audio, device, lead)
        log.info("done — confirm it was heard clearly on the device.")
        return

    from wave_dispatch import get_controller
    tg = args.talkgroup or (s.get("wave") or {}).get("talkgroup", "all-restaurants")
    wave = get_controller(s)
    wave.start()
    try:
        log.info("STAGE 2: key '%s' -> play %s -> release", tg, audio)
        wave.key(tg)
        play(audio, device, lead)
    finally:
        wave.unkey()
        wave.stop()
    log.info("done — check logs + logs/dispatch_*.png; confirm heard on the device.")


if __name__ == "__main__":
    main()
