# presence-desk-1108 (INBOX 1692, desk companion presence)

Branch `agent/presence-desk-1108`. Technique only from the games it was briefed on; no art, names or look copied.

## Done, with numbers (fake transport, fixed clock, seeded)

- D1 presence spells: one long prop act (2 to 8 min) chosen by hour and mood (`presence.py`), between spells a seen move. Standing still went from about 50 of every 60 minutes to 10.6 min an hour; pictures in a spell 6 a second down to about 3.35 (FLOW_SPELL_MS 300). Typing keeps the spell going in place. A menu command ends it.
- D2 canvas margin: any effect grows the canvas (`fx_margin`), the figure's box moves by the pad; a ring, sparkle or cloud is never clipped.
- D3 travel modes: blink (sparkle), cloud ride, bubble drift, and a caret move that picks among blink, portal and puff. Long legs: 57 percent flourishes (was 20 to 40), short legs 36.
- D4 round fx strength, D6 startup log line (`effects=on` or `effects=off, every move is a fade (animations are off in <reason>)`).
- App side (commit 94171439): edge wrap with exit and entry, sparkle blink, cloud ride, bubble drift, tab-switch crossfade as a blink; help text in the popover and the companion-travel topic.

## Intent moved (tests changed, each with a note)

- Stillness tests (float, alive_1670, rest_life, life_1670, rest_1670, parity, smooth, nap, wander) run with `presence = False`: spells have their own tests in `tests/test_overlay_presence_1692.py`.
- The 80 percent on-foot ratchet is now 45 percent, the flourish bounds 0.62 long and 0.42 short, a long leg walked 16 of 40.
- `ACTS` has `spell`; busy typing may show the spell act in place, never a travel.
- Rest sim: settled median bar 45 to 35 s, wakes a minute cap 480 to 500 (cloud rides and bubble drifts are drawn every frame).

## Unverified

- Windows: nothing here ran on a real layered window. Effects, pad moves and the spell prop pictures are tested against the fake only.
- Real display: no screenshot of the sparkle, cloud or bubble; only pixel and box numbers.

## Left

- D5 edge spots and perch spells (sit on a window top for a spell).
- A2 sweep for far moves (the companiontravel.js sweep is not in this worktree).
- A4 in-app presence spells.
- `warps` counts in `tests/overlay_sim_1670.py` for blink, cloud and bubble, including the no-windows case.

## Found, not fixed

- `tests/test_overlay_ride_1670.py::test_no_frame_is_cut_on_a_ride_over_a_seeded_run[walk-*]` fails on the base commit too: a fly to a hang point puts the box 29 to 32 px above the work area top.
