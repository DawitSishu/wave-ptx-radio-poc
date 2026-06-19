"""
PTT transmit adapters.

The engine only ever calls adapter.transmit(audio_path, talkgroup). It does not
care HOW the audio gets out. That keeps the scheduling/engine code stable while
the transmit mechanism evolves:

    loopback  (Phase A)  -> play + log, no real transmit
    dispatch  (Phase B)  -> drive the WAVE PTX Dispatch web console
    (future)             -> an official WAVE PTX API, if one becomes available
"""
import logging
import time

import numpy as np
import sounddevice as sd
import soundfile as sf

log = logging.getLogger("ptt")


def get_adapter(settings):
    if settings.get("ptt_adapter") == "dispatch":
        return DispatchAdapter(settings)
    return LoopbackAdapter(settings)


def _play(audio_path, settings):
    """Play audio to the configured output device (the VB-Cable input)."""
    data, samplerate = sf.read(audio_path, dtype="float32")
    lead = settings.get("ptt_lead_silence", 0.5)
    if lead:
        pad = np.zeros((int(samplerate * lead),) + data.shape[1:], dtype="float32")
        data = np.concatenate([pad, data])
    sd.play(data, samplerate, device=settings.get("output_device"))
    sd.wait()


class LoopbackAdapter:
    """Phase A: validate the whole engine without a real radio transmit.

    Plays the clip (so audio levels/quality can be checked) and logs it as if
    sent. Lets us prove scheduling, file handling, timing and alerts before the
    Dispatch license is live.
    """

    def __init__(self, settings):
        self.settings = settings

    def transmit(self, audio_path, talkgroup):
        log.info("[loopback] would transmit %s -> %s", audio_path, talkgroup)
        _play(audio_path, self.settings)
        return True


class DispatchAdapter:
    """Phase B: drive the WAVE PTX Dispatch web console.

    Flow: select talk group -> press PTT -> wait for the talk-permit grant ->
    play audio through VB-Cable into Dispatch's mic -> release PTT. A busy floor
    is retried with backoff.

    The console interactions below are stubbed: the real selectors get filled in
    once the Dispatch license is live and the console DOM is visible. Everything
    around them (timing, retries, audio, logging) is already done.
    """

    def __init__(self, settings):
        self.settings = settings
        self._page = None  # Playwright page, created in connect()

    def connect(self):
        raise NotImplementedError(
            "Phase B: launch Playwright, log into Dispatch, open the console."
        )

    def transmit(self, audio_path, talkgroup):
        s = self.settings
        retries = s.get("ptt_busy_retry", 3)
        for attempt in range(1, retries + 1):
            if self._select_talkgroup(talkgroup) and self._press_ptt():
                if self._wait_for_grant(s.get("ptt_grant_wait", 1.0)):
                    _play(audio_path, s)
                    time.sleep(s.get("ptt_tail_hold", 0.3))
                    self._release_ptt()
                    log.info("[dispatch] transmitted %s -> %s", audio_path, talkgroup)
                    return True
                self._release_ptt()
            log.warning("[dispatch] floor busy/denied (%d/%d) -> %s",
                        attempt, retries, talkgroup)
            time.sleep(s.get("ptt_busy_backoff", 5))
        return False

    # --- console interactions: filled in Phase B once Dispatch is reachable ---
    def _select_talkgroup(self, talkgroup):
        raise NotImplementedError

    def _press_ptt(self):
        raise NotImplementedError

    def _wait_for_grant(self, timeout):
        raise NotImplementedError

    def _release_ptt(self):
        raise NotImplementedError
