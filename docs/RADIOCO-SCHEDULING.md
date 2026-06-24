# Radio.co scheduling + dead air (how to time the prompts)

Radio.co is a **continuous broadcast** platform — it never plays silence. If there's
a gap with nothing scheduled, it auto-fills by looping a playlist. So to get prompts
that play at specific times (instead of looping back-to-back), you schedule the
prompts **and** program **dead air** (silence) for the gaps.

## How this works with our system

The relay only transmits tracks whose title matches the prompt filter
(`relay_match`, set to `SERGEANT`). That means:

- **Prompts** (`SERGEANT_…`) → relayed to the radios.
- **Dead air / silence / any filler** → ignored. The relay does **not** key the
  radios during it.

So Radio.co decides **when** a prompt airs; the relay just mirrors it and filters to
prompts only. **Schedule changes in Radio.co need no code changes.**

## Two ways to schedule

**A. Scheduled events (precise per-prompt timing) — best for exact times.**
Schedule each prompt (or a small playlist) as a timed event in Radio.co's
**Schedule**. Radio.co fires it at that clock time; the relay airs it then. Most
precise, but more entries to set up.

**B. One playlist with silence tracks for spacing — simplest for "every X min".**
Build a playlist that alternates **prompt → silence track (~13–15 min) → prompt →
silence → …** and schedule it across the operating window (8am–4am). The silence
tracks create the gaps. Note: this plays sequentially, so timing **drifts** over the
day (it's "every ~15 min," not clock-locked).

For exact times (e.g., 8:00 sharp), use **A**. For "a reminder roughly every 15
minutes," **B** is easier.

## Practical notes

- **Name prompts so they match the filter:** keep the `SERGEANT_…` naming so the
  relay airs them. (If the naming convention changes, update `relay_match` in
  `config/settings.yaml` — a one-line config edit, no code change.)
- **Name silence/dead-air tracks anything else** (e.g. `SILENCE_…`) so the relay
  ignores them.
- **Timezone:** set it on the Radio.co station (Mason set it to CST). The relay
  follows whatever Radio.co plays, so the station's timezone is the source of truth —
  no change needed on our side.
- The exact click-path for events/playlists lives in Radio.co's **Schedule** and
  **Playlists** sections — confirm against their UI / help docs, as it changes.

## TL;DR

Radio.co owns the **timing** (schedule + dead air). The relay owns the **delivery**
(airs only prompts, ignores the rest). Set the schedule up in Radio.co and the radios
get the right prompt at the right time — no code changes.
