# Phase B — Live transmit to the radios (plan)

Phase A is done: Radio.co's broadcast is relayed onto the VM and into **VB-Cable**,
running 24/7. Phase B takes that audio the last hop — out to the **Motorola TLK 25
radios** via **WAVE PTX**.

## The hard gate

WAVE PTX is a closed system. We cannot transmit to the radios without WAVE access.
There is no public/keyless path (unlike Radio.co's stream). So Phase B is blocked
until **one** of these is available:

- **WAVE PTX Dispatch** — the browser console, once the license registers. (Planned path.)
- **WAVE Communicator seat** — the desktop/mobile app. If the license includes one,
  we can test transmit *earlier*, before full Dispatch setup. (Fast-start option.)

## Architecture (the last hop)

```
[Phase A, done]                         [Phase B]
Radio.co --> VM relay --> VB-Cable --> WAVE PTX --> talk group --> TLK 25 radios
                          (mic in)     (auto PTT     (all/selected
                                        when a        locations)
                                        prompt airs)
```

The relay already knows when a prompt is airing (its `RELAYING` state). Phase B hooks
that signal to **key WAVE's push-to-talk** for the duration of the prompt.

## Build steps (once we have WAVE access)

1. Log into **WAVE PTX Dispatch** on the VM; join the **test talk group**.
2. Set **CABLE Output (VB-Audio)** as Dispatch's **microphone** input (VB-Cable now
   feeds WAVE instead of just staging).
3. Build the **PTT trigger**: when the relay starts airing a prompt, automate
   press-and-hold on the talk group; release when the prompt ends. (Browser
   automation against the live console — selectors filled against the real DOM.)
4. **Timing**: press PTT -> wait for the talk-permit grant -> audio flows -> release.
   (Lead-in/cushion already handled upstream.)
5. **Floor control**: if the channel is busy, wait + retry.
6. **Validate**: a Radio.co prompt transmits and plays clearly on a real TLK 25,
   with a logged confirmation + the existing Slack alert on failure.
7. **Talk-group selection**: one big group = all 10 locations; per-location groups =
   send to one. (Supports "all restaurants or just one.")

## What's needed from Mason to start

- **WAVE PTX Dispatch login** (license registered) **and one talk group**, OR
- confirmation the license includes a **Communicator seat** + its login (fast-start), and
- **1-2 TLK 25 radios** (or the WAVE app) to receive on.

Everything upstream is done, so once WAVE access is in hand, Phase B is the quick part.
