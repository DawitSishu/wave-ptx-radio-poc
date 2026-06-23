"""
WAVE PTX transmit control (Phase B).

When the relay airs a prompt, this keys WAVE's push-to-talk on a talk group so the
audio (already on VB-Cable) goes out to the radios, and releases when it ends.

Modes (settings -> wave.mode, or the WAVE_MODE env var):
  off       - no transmit (Phase A: relay only feeds VB-Cable)
  sim       - SIMULATE ptt (logs press/grant/release). Testable with no WAVE account.
  dispatch  - drive the real WAVE PTX Dispatch web console via Playwright.

The `dispatch` flow is fully implemented; the only thing it needs once the license
is live is the console's CSS selectors, which are read from settings (wave.selectors)
-- so wiring it to the real console is a config edit, not a code change.
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
    """Phase A: no transmit. The relay just feeds VB-Cable."""

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
    """Drive the real WAVE PTX Dispatch web console with Playwright.

    Selectors come from settings.wave.selectors so the live console can be wired up
    without touching code:
        wave:
          dispatch_url: "https://...dispatch console url..."
          username: "..."
          password: "..."
          selectors:
            username: "#email"
            password: "#password"
            submit:   "button[type=submit]"
            talkgroup: "[aria-label='{talkgroup}']"   # {talkgroup} is substituted
            ptt:       "button.ptt"
            granted:   ".talk-permit-granted"
    """

    def __init__(self, settings):
        self.w = settings.get("wave") or {}
        self.sel = self.w.get("selectors") or {}
        self.grant_wait = self.w.get("grant_wait", 1.0)
        self.busy_retry = self.w.get("busy_retry", 3)
        self.busy_backoff = self.w.get("busy_backoff", 5)
        self._pw = None
        self._browser = None
        self._page = None
        self.keyed = False

    def start(self):
        from playwright.sync_api import sync_playwright  # lazy import
        url = self.w.get("dispatch_url")
        if not url:
            raise RuntimeError("wave.dispatch_url not set in settings")
        self._pw = sync_playwright().start()
        # visible browser: the Dispatch console needs a real interactive session
        self._browser = self._pw.chromium.launch(headless=False)
        self._page = self._browser.new_page()
        self._page.goto(url)
        if self.sel.get("username") and self.w.get("username"):
            self._page.fill(self.sel["username"], self.w["username"])
            self._page.fill(self.sel["password"], self.w["password"])
            self._page.click(self.sel["submit"])
            self._page.wait_for_load_state("networkidle")
        log.info("[dispatch] WAVE console opened: %s", url)

    def key(self, talkgroup):
        if self.keyed:
            return
        page = self._page
        tg = self.sel.get("talkgroup")
        ptt = self.sel.get("ptt")
        granted = self.sel.get("granted")
        for attempt in range(1, self.busy_retry + 1):
            if tg:
                page.click(tg.format(talkgroup=talkgroup))
            el = page.query_selector(ptt)
            box = el.bounding_box()
            page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
            page.mouse.down()                       # press and HOLD
            try:
                if granted:
                    page.wait_for_selector(
                        granted, timeout=int(self.grant_wait * 1000) + 3000)
                else:
                    time.sleep(self.grant_wait)
                log.info("[dispatch] talk-permit granted -> %s", talkgroup)
                self.keyed = True
                return
            except Exception:  # noqa: BLE001 - floor busy / no grant
                page.mouse.up()
                log.warning("[dispatch] floor busy (%d/%d) -> %s",
                            attempt, self.busy_retry, talkgroup)
                time.sleep(self.busy_backoff)
        log.error("[dispatch] could not get the floor for %s", talkgroup)

    def unkey(self):
        if not self.keyed:
            return
        try:
            self._page.mouse.up()                   # release PTT
        except Exception as e:  # noqa: BLE001
            log.error("[dispatch] release failed: %s", e)
        self.keyed = False
        log.info("[dispatch] PTT released")

    def stop(self):
        try:
            self.unkey()
        finally:
            try:
                if self._browser:
                    self._browser.close()
                if self._pw:
                    self._pw.stop()
            except Exception:  # noqa: BLE001
                pass
