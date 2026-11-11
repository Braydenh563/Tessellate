# compalive-1109: what is left

Branch agent/compalive-1109. Done: 1e96de2 (INBOX 1709, resolved), adf9960 (1710, five reactions to the app), c17eeeb (1710 eleven acts to the desk, 1711 four new acts), merge e849f31.

## INBOX 1709 (resolved)
- Not verified: how the bending reads in motion to the eye (numbers only: 0 of 64 paths changed shape before, 62 of 64 after); Firefox and Safari draw `d` set by script the same, but only Chromium was run.
- Idle script cost: about 15 ms a second by a microbench (1.5 ms a tick, 10 ticks a second); the CDP task totals were too noisy to give a before and after (170 to 770 ms a second both ways, the headless raster). Worth one run of the audit's own row 55 probe.
- Not done: hair locks (55 paths) and the tail keep their own motion; a velocity-driven lag for the ribbons (the tail chain already carries the boxes: `atlasTailFollow.strands`).

## INBOX 1710 (partly)
- Desk-only left: `react.window_opened`, `window_closed`, `window_dragged` (a page is never told: no meaning in a browser).
- App-only left (22, tests/test_companion_catalogue_1108.py `APP_ONLY`; W31 E1, E2 moved `act.dangle`, `act.kick_legs`, `act.hang_one_hand`, `pos.cross_legged`, `pos.edge_dangle` to the desk with five frames, see HISTORY; comp2-1109 moved `act.meditate`, `act.lounge`, `act.rest_head` to the desk with `YIELD_TO_SIT` in the engine; w31 moved the eight note and search reactions, below): the hangs (`hang_by_feet`, `sloth`), `chair`, `lower.drift`, `move.afield`, the positions `back_float`, `lean`, `lounge` (the act is on the desk as the sit settled low; no second sit picture), and 13 transitions.
- Weights parity (test_companion_weights_1108, tolerance 3.6): the test ran slowly here and printed no failure; not re-measured for the gap itself (39.1 against 35.7 before).
- Not verified: the four new acts' look in motion (the companion sat at the page's top edge in the sweep, so only the applied variables were measured); the desk's twelve new acts were not rendered.

## INBOX 1711 (partly)
- Built: sneeze, hiccup, hug, foot tap (both sides).
- Built (comp2-1109, both sides): a firefly chase (`firefly`, `act.star_catch`), a star pile (`starpile`, `act.count_stars`), a nap on a note card (`cardnap`, `act.card_nap`) and a wave at the pointer (`wavepointer`, `act.wave_pointer`). Built (nap1711-1109, app side): the wave is the idle trigger alone (8 s, measured 8029 ms) and the card nap needs a visible card perch (`nmb.cardEdge`; seat 128 against card top 128.19). Left: the desk's card nap (needs a note-card box), and the app does not walk to a card to nap, it naps only when it already sits on one. Not verified: the look in motion (numbers only: animation names on arm, eye, tail and grin while the class is set); the desk's new acts were not rendered.
- The other backlog acts with no prop: `tail_stretch`, `self_hug` is done, `kneel_look`, `stargaze_awake`, `cloud_pillow`, `tail_chase`, `knit_starlight`, `paper_plane`, `blow_bubbles`, `conduct`, `lean_on_edge`, `balance_walk`, `sketch_view`.

## Found, not fixed
- tests/test_frontend_wake_sources.py fails on the base branch (documents-callouts.js raf 0 to 1; documents.js 13 now 12): not mine. **Stale:** tests/test_frontend_wake_sources.py passes on head (checked 2026-11-09).
- tests/test_overlay_idle.py `test_a_wake_lands_on_a_new_frame_not_the_same_one_again` and `test_a_blink_still_overrides_the_cycle` fail on the base branch. **Stale:** tests/test_overlay_idle.py passes on head (checked 2026-11-09).
- `companion-catalogue.json` had no entry for the desk face `blink` (INBOX 1704); named under `face.calm`. **Fixed desklane-1109 (the desk face blink has its own catalogue row).**

## desklane-1109 (done 2229e7a, 89394b9; INBOX 1718 resolved)
- Left (1696 aa): the plant pot held in the tail curl needs a tail-curl frame. (1696 kk): hold still, carry over, catch mid-air, tail pull, drag skid, toss up and pointer chase are built on neither side (catalogue `int.*` missing).
- Left (1710 b): desk needs frames for hang_by_feet, sloth, chair, pos.lean/lounge/back_float.
- Left (1711): the card nap still curls on nothing (needs a note-card box).
- Not verified: real Windows (FakeWin32 only); the entrance, wave and menu line in motion; the in-app wave trigger was read as text, not driven in a browser.
- Fixed here: the desk face blink has its own catalogue row; test_overlay_idle's two base failures pass on this branch.

## w31 events feed (built; INBOX 1710 b, the eight note and search reactions)
- Built: `core/companion_events.py` keeps a ring of 64 `{id, kind, at}` (monotonic ids, a per-kind gap, nothing else: no title, text, note id or query; a private note is only ever `private_note`; no route serves it). The server notes: `GET /search` page 1 (`search_nothing`, and `search_found` only within 30 s of a miss, as the app), `GET /entries/{id}?open=1` (`long_note` over 1200 characters, `private_note` for a private note or a private space), `DELETE /entries/{id}` (`note_binned`, or `private_note`), `GET /graph` (`graph_laid`, 60 s gap), `GET /remarks` with a line to say (`remark`, 600 s gap), the reminder notifier's due tick (`reminder_bell`). The overlay reads it in `ScreenWatch.poll` (every 2 s, only on the ground, so not on the fall tick; the first read after a start or a resume is history, an event older than 20 s is not news) and answers with `extras.REACTIONS` rows made of poses the desk ships: `graph_laid` glance_screen, `long_note` peek_back, `remark` poke_curious, `search_found` nod_done, `reminder_bell` a new act `bell_ring` on the `wave` pose, `note_binned` a `wince`, `private_note` a `cover_eyes` duck and `search_nothing` a `puzzle_tilt` (new acts on the `look` and `stand` poses, with the worried, shy and confused faces). Tests: tests/test_companion_events_feed.py (the ring, the routes, the watch, and the running overlay answering each of the eight on a fake).
- Left, honestly less than the app: no reading glasses (long_note is a long look back; a prop), no hands over the eyes (private_note is a shy face and a duck), no speech bubble for a remark (the desk would hear that one is ready, never its words), the graph reaction fires when the tab loads, not on a layout change (the server cannot see a layout change). `reminder_bell` plays only while no card is up (the card, with its bell, is the other answer).
- Not verified: real Windows (FakeWin32 and the fixed clock only); the look of the eight in motion on the desk; an overlay in a separate process from the server would see an empty ring (desktop mode runs both in one process).

## w31 frames the desk still lacks (nothing drawn; app-only acts that need new art)
Every desk pose is one PNG per look, same canvas for all of a look's frames: feminine 275 x 298 px, masculine 289 x 304 px (twice the CSS size; `scripts/render_desk_frames.js` captures the live rig, `render_desk_frames.py` solidifies, crops to the shared `crop_box` and quantises). A new pose is a row in `render_desk_frames.js`, a name in `sprites.FRAME_NAMES` (a look without it must keep working) and an act in `behaviour.py`/`extras.py` that names it. Counts below are poses per look, so double them for the two looks. Seen in-betweens (`trans.*`) are separate and not counted; the pose dissolve in `sprites.py` stands in until they exist.
- `hang_by_feet` (`act.hang_by_feet`): one pose `hang_feet`, same size, upside down: knees hooked over the edge at the frame's top, arms and hair falling, tail drooping (the frame is the `hang` canvas turned head down, not a rotation of it).
- `sloth` (`act.sloth`): one pose `hang_sloth`, same size, `hang` with all limbs limp, head sunk between the arms; two frames if the sway is to read (`hang_sloth0`, `hang_sloth1`), one if the engine's sway keys do it.
- `chair` (`act.chair`): no new body frame (`sit` exists); missing is the prop, a chair drawn in code in `props.py` (like `_journal`), a seat and a back behind the `sit` frame sized to its 275 x 298 canvas. That is code, not art.
- `lean` (`pos.lean`, `act.peek_side`, `act.lean_on_edge`): one pose `lean`, same size, the figure leaning a shoulder on a vertical edge, weight on one leg, near arm folded; it needs a side edge to stand against (the engine has none, only top edges: `perches.top_edges`), so the perch finder is also missing.
- `lounge` (`pos.lounge`): one pose `lounge`, same size, propped on one hand, one knee up, tail curled; `act.lounge` is already on the desk through `sit`, so this is only the nicer rest pose.
- `back_float` (`pos.back_float`, `act.stargaze_awake`): one pose `back_float`, same size, on its back in the air, face up, arms behind the head, tail trailing; `lower.drift` needs no frame (the desk's flow offsets are `behaviour.Flow`) and `move.afield` needs none (an engine trip, not a pose).
