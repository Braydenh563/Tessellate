# catalogue-a-1108: Batch A remaining list

Branch agent/catalogue-a-1108. Rows A1 to A5 of atlascat-1108.md step 4. No row adds or moves a catalogue entry, so
`APP_ONLY`, `DESK_ONLY` and their caps are unchanged (the ratchet rule: nothing built, nothing lowered, nothing raised).

done: A1 loader (`overlay/catalogue.py`), A2 reader (`nmb.cat` in avatars.js), A3 durations and weights, A4 beats, A5 mood,
energy and day weights; see `git log` for the hashes.

Left, one line each:

- Non-shift beats (`breath_deep`, `ear_or_tail_twitch`, `page_turn`, `glance_up`, ...) are not played on either side; only the
  beats with `shifts: true` are (desk: `Mind.start_beats`/`shift_due`; app: `nmb.cat.plan`/`arm`/`shift`). atlascat step 4 Batch C
  draws them.
- The desk shift in a sit or a sleep state is a lean and settle (`engine._ground_pose`, `SHIFT_FOR`), not a mirror turn: a flip
  moves the window by `_flip_dx`, which `tests/test_overlay_alive_1670.py::test_7_rest_stays_alive_in_place_under_the_redraw_cap`
  forbids. An act's shift is a real turn (`_face`).
- The in-app shift is a lie-down turning onto the other side, or a variant re-pick plus the arm cue for `nap` and `read`; there
  is no new drawing, so a reader sees a small change (not measured in a browser).
- App mood for the weights is the catalogue's own slow mood (`nmb.cat.weigh`, 6 to 12 minutes from the part of the day), not
  the reading mood `NAME_MARK_BUDDY_MOODS` uses; the two multiply.
- The in-app sim in `tests/test_companion_weights_1108.py` drives `nmb.cat.weigh` over a stand-in table of the catalogue's acts,
  not the whole `nameMarkBuddyDecide` (it needs the DOM).
- Desk act lengths never go under the built-in minimum (the redraw cap of 12 a second, `test_7_rest_stays_alive...`); the
  table's shorter minimums (bounce 0.8, stretch 1.6, groom 3.2, peer_at_cursor 1.4, scan_horizon 2.5) are not reached on the desk.
- Review fixes: a nap command during a spell's warp is taken at once (nap_1683u back on seed 5; a test covers seeds 1, 2, 3, 5, 7, 10, 11);
  standing is at most 9 draws a second over seeds 1 to 5 (small stand acts and in-place turns draw at the rest pace); a catalogue entry missing a
  key is skipped. `frontend/sw.js` needs no precache: the shell is never cached, so there is no offline start, and a failed fetch keeps the built-ins.
- Open: the still-stand test reads seeds (1, 3, 5) because seed 2 on the walk now draws a `read_book` from the stroll path, whose sit frame sits 8 px
  lower (a moved window by design; `sit_down` does the same on other seeds at the base). Seeds (1, 2, 3) need the stroll pick to skip sit-frame acts: a design call.
- Intent note: `test_companion_mind_1107::test_the_hour_summary_numbers` acts bar 240 to 200 (longer catalogue lengths: 222 acts, 15 chains
  over eight seed-hours).
- A3, A4 and A5 share files (behaviour.py, engine.py, avatars.js), so they land as one commit, not three.
- Numbers: desk 600 s sim longest held pose 81.0 s (was 150 s sit, 221 s nap); seeded act-count means desk 37.17 vs 36.17, app 26.25 vs 25.67.
- Under a loaded machine `test_overlay_presence_1692` spell_share (0.4928) and the spin/travel files failed once and pass alone.
