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
- `tests/test_overlay_nap_1683u.py::test_its_own_long_nap_ends_with_a_stretch` seed 5 to 4: at seed 5 the first update starts a
  spell and drops the nap command (also at the base), and its stretch was a chance idle one.
- Found, not fixed: a `nap` command given while the engine is walking to a spell spot is dropped (`_nap` only runs from
  stand); 7 of 11 seeds show it at the base.
- Two more intent notes: `test_overlay_rest_life_1670` stand test reads seeds (1, 3, 5) (seed 2 now draws a dust_off or a read_book in the
  first minute); `test_companion_mind_1107::test_the_hour_summary_numbers` acts bar 240 to 200 (longer catalogue lengths: 222 acts, 15 chains
  over eight seed-hours).
- A3, A4 and A5 share files (behaviour.py, engine.py, avatars.js), so they land as one commit, not three.
- Numbers: desk 600 s sim longest held pose 81.0 s (was 150 s sit, 221 s nap); seeded act-count means desk 37.17 vs 36.17, app 26.25 vs 25.67.
- Under a loaded machine `test_overlay_presence_1692` spell_share (0.4928) and the spin/travel files failed once and pass alone.
