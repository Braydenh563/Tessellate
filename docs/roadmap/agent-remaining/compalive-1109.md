# compalive-1109: what is left

Branch agent/compalive-1109. Done: 1e96de2 (INBOX 1709, resolved), adf9960 (1710, five reactions to the app), c17eeeb (1710 eleven acts to the desk, 1711 four new acts), merge e849f31.

## INBOX 1709 (resolved)
- Not verified: how the bending reads in motion to the eye (numbers only: 0 of 64 paths changed shape before, 62 of 64 after); Firefox and Safari draw `d` set by script the same, but only Chromium was run.
- Idle script cost: about 15 ms a second by a microbench (1.5 ms a tick, 10 ticks a second); the CDP task totals were too noisy to give a before and after (170 to 770 ms a second both ways, the headless raster). Worth one run of the audit's own row 55 probe.
- Not done: hair locks (55 paths) and the tail keep their own motion; a velocity-driven lag for the ribbons (the tail chain already carries the boxes: `atlasTailFollow.strands`).

## INBOX 1710 (partly)
- Desk-only left: `react.window_opened`, `window_closed`, `window_dragged` (a page is never told: no meaning in a browser).
- App-only left (38, tests/test_companion_catalogue_1108.py `APP_ONLY`): the long sitting acts `act.meditate`, `act.lounge`, `act.rest_head` (on the desk's sit frame they held off its sit at ten minutes idle: test_overlay_idle `first_sit` 636 against 600 to 610; give the engine a "yield the sit" rule first), the hangs (`dangle`, `hang_by_feet`, `hang_one_hand`, `sloth`), `chair`, `kick_legs`, `lower.drift`, `move.afield`, the positions `back_float`, `cross_legged`, `edge_dangle`, `lean`, `lounge`, the reactions `graph_laid`, `long_note`, `note_binned`, `private_note`, `remark`, `reminder_bell`, `search_found`, `search_nothing` (the desk gets no note or search events: needs an events feed from the app's server to the overlay), and 13 transitions.
- Weights parity (test_companion_weights_1108, tolerance 3.6): the test ran slowly here and printed no failure; not re-measured for the gap itself (39.1 against 35.7 before).
- Not verified: the four new acts' look in motion (the companion sat at the page's top edge in the sweep, so only the applied variables were measured); the desk's twelve new acts were not rendered.

## INBOX 1711 (partly)
- Built: sneeze, hiccup, hug, foot tap (both sides).
- Left from the owner's list: chasing a firefly or wisp (`act.star_catch`), a little star pile (`act.count_stars`), napping curled on a note card edge (new, needs the card geometry), waving at the pointer after a pause (a pointer-idle trigger on both sides). Stargazing (`stars`), reading (`read`), dusting (`dust_off`), humming (`hum`), peeking (`peek`) and stretching (`stretch`, `yawn`) already exist.
- The other backlog acts with no prop: `tail_stretch`, `self_hug` is done, `kneel_look`, `stargaze_awake`, `cloud_pillow`, `tail_chase`, `knit_starlight`, `paper_plane`, `blow_bubbles`, `conduct`, `lean_on_edge`, `balance_walk`, `sketch_view`.

## Found, not fixed
- tests/test_frontend_wake_sources.py fails on the base branch (documents-callouts.js raf 0 to 1; documents.js 13 now 12): not mine.
- tests/test_overlay_idle.py `test_a_wake_lands_on_a_new_frame_not_the_same_one_again` and `test_a_blink_still_overrides_the_cycle` fail on the base branch.
- `companion-catalogue.json` had no entry for the desk face `blink` (INBOX 1704); named under `face.calm`.
