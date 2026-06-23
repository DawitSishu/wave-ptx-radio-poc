"""
WAVE PTX transmit control (Phase B).

When the relay airs a prompt, this keys WAVE's push-to-talk on a talk group so the
audio (already on VB-Cable) goes out to the radios, and releases when the prompt ends.

Modes (settings -> wave.mode):
  off       - do nothing (Phase A behaviour: relay only feeds VB-Cable)
  sim       - SIMULATE ptt (logs press / grant / release). Testable NOW, no WAVE
              account needed - proves the relay -> PTT integration end to end.
  dispatch  - drive the real WAVE PTX Dispatch web console via Playwright. The flow
              is implemented; the DOM SELECTORS must be verified against the live
              console once the license is registered.

Key flow (real + sim): key() -> press PTT -> wait for talk-permit grant -> hold
while the prompt plays -> unkey() -> release. A busy floor is retried with backoff.
"""
import logging
import os
import time

log = logging.getLogger("wave")


def get_controller(settings):
    # WAVE_MODE env var overrides settings (handy for testing without editing config)
    mode = (os.environ.get("WAVE_MODE")
            or (settings.get("wave") or {}).get("mode") or "off").lower()
    if mode == "dispatch":
        return DispatchController(settings)
    if mode == "sim":
        return SimController(settings)
    return NullController(settings)


class NullController:
    """Phase A: no transmit at all. The relay just feeds VB-Cable."""

    def __init__(self, settings):
        self.mode = "off"

    def start(self):
        log.info("WAVE transmit OFF (relay feeds VB-Cable only)")

    def key(self, talkgroup):
        pass

    def unkey(self):
        pass

    def stop(self):
        pass


class SimController:
    """Simulate PTT so the Phase B integration is testable without WAVE access."""

    def __init__(self, settings):
        self.mode = "sim"
        w = settings.get("wave") or {}
        self.grant_wait = w.get("grant_wait", 1.0)
        self.keyed = False

    def start(self):
        log.info("WAVE transmit SIM ready (logs PTT, no real transmit)")

    def key(self, talkgroup):
        if self.keyed:
            return
        log.info("[sim] PTT press -> talkgroup '%s'", talkgroup)
        time.sleep(self.grant_wait)
        log.info("[sim] talk-permit GRANTED -> transmitting to radios")
        self.keyed = True

    def unkey(self):
        if not self.keyed:
            return
        log.info("[sim] PTT release -> stopped transmitting")
        self.keyed = False

    def stop(self):
        self.unkey()


class DispatchController:
    """Drive the real WAVE PTX Dispatch web console (Playwright).

    The control flow is built; the items marked SELECTOR are placeholders to fill
    against the live Dispatch DOM once the license is registered.
    """

    # --- SELECTOR: verify all of these against the live Dispatch console ---
    LOGIN_URL = None       # the Dispatch console URL
    SEL_TALKGROUP = None   # a talk-group tile, formatted with the group name
    SEL_PTT = None         # the push-to-talk button
    SEL_GRANTED = None     # the "you have the floor" / talk-permit indicator

    def __init__(self, settings):
        self.mode = "dispatch"
        self.w = settings.get("wave") or {}
        self.grant_wait = self.w.get("grant_wait", 1.0)
        self.busy_retry = self.w.get("busy_retry", 3)
        self.busy_backoff = self.w.get("busy_backoff", 5)
        self._page = None
        self.keyed = False

    def start(self):
        raise NotImplementedError(
            "Phase B: launch Playwright, open the Dispatch console (LOGIN_URL), and "
            "log in with wave.username / wave.password. Fill the SELECTORs against "
            "the live console DOM.")

    def key(self, talkgroup):
        # select talk group -> mousedown PTT -> wait for SEL_GRANTED (retry if busy)
        raise NotImplementedError(
            "Phase B: select the talk group, press-and-hold PTT, and wait for the "
            "talk-permit grant. Retry busy_retry times with busy_backoff on a busy floor.")

    def unkey(self):
        raise NotImplementedError("Phase B: release PTT on the live console.")

    def stop(self):
        try:
            self.unkey()
        except Exception:  # noqa: BLE001
            pass
