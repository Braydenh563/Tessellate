# deskframes-1108: the desk frames re-rendered (INBOX 1696 x, w, z, hh; atlasm-1108 step 5)

## Done

- Render fixed (`scripts/render_desk_frames.js`): every frame's live tail (`atlasTail`) sits at one moment (the idle
  loop's start for a non-idle frame), the breath and lower-wisp skew too; the rig's own CSS sways (`atl-sway*`,
  `atl-lw-sway*`) are held mid-swing and the other non-act CSS animations at 0, so `at` (the act's moment) no longer
  moves the lower body (stand, blink, look, wave and land were 5 to 7 px apart); the page's blink clock is stopped
  and its `atl-blinking` classes removed (a masculine `stand` shipped with shut eyes). Walk tail swing 11 to 9 deg,
  lower skew 9 to 8 deg (the pinned sways made the walk dip 12 px under stand, test bound 4 at the feet line).
- `render_desk_frames.py`: `clip_idle_tails` clips to the stand's bottom (was +1), so the idle cycle is one row.
- Frames re-rendered, both looks: 54 files each (56 names less the 2 card frames); masculine 262x303, feminine
  263x296 at the last render (the crop box moves a few px per render: re-measure `LID_EYES` after every render).
- `LID_EYES` measured from the mouth ink (MOUTH_DOWN 13 below the eye line): masculine (110,109,155,125), feminine
  (109,109,154,125). The atlasm estimate (109,111,155,127) was 2 px low.
- `faces.py` mouth (INBOX 1696 hh): the calm mouth is painted out from the skin either side of it, row by row, with a
  feathered edge, not a flat disc of the between-the-eyes tone (35 to 63 levels off the face, 10 to 13 now).
- `capture.CAPTURED` leaves out the optional wave frames; `complete()` needs CAPTURED plus the cards.
- Tests: `tests/test_overlay_deskframes_1696.py` (eyes open in stand and the eye box on them, the mouth patch, the
  solidify growth in px); `test_overlay_sprites.py` 50 to 56 and the optional-wave count (Intent moved notes).

## Measured

- Arm (feminine wave2, perpendicular, 2x capture): coverage 5.75 raw to 6.63 solid (+0.88); half-alpha width
  5.34 to 6.54 (+1.2). At 128 px figure height (x 128/306): +0.37 and +0.5 px, under the 1 px bar: ramp unchanged,
  the ratchet pins it (`SOLID_LO` 24, `SOLID_HI` 120: at most +1.0 px at 2x for a soft edge).
- Mouth patch: 44 to 48 levels off the surrounding skin (flat disc, old code) to 10 to 13 (cause: one flat tone
  from `_skin(patch, ox, oy)` over an ellipse 16.5 x 8 px; the face is shaded there and the eye anchor is not always
  on the eyes).

## Left

- Eye boxes depend on the crop box: a later `render_desk_frames.py` run needs `LID_EYES` re-measured (mouth ink
  centre minus 13 for the eye line; `scratchpad` has no tool, the three-line probe is in the commit message).
- The blush ellipses in `faces._mouth` paint a faint green-tinted ring where they overhang the face edge (masculine
  `content`/`smile`, seen on the mouth sheet); not fixed.
- Not verified on a real desktop (Windows overlay): frames checked as PNG crops and the targeted pytest only.

## Still failing with these frames (all pass on the merge base with the old frames; targeted run, `-n 3 -p no:randomly`)

- `test_overlay_ride_1670.py`: `test_the_lowest_drawn_row_of_every_resting_frame_is_on_the_work_areas_bottom[feminine]`
  (walk5 gap -5, bound 4: the feminine walk tail dips 11 px under stand, was 8), `test_no_frame_is_cut_on_a_ride_over_a_seeded_run`
  (all four: left, right or top cut by 1 to 2 px).
- `test_overlay_land_1683.py::..._bounded_time[corner-float]` (1.55 s), `test_overlay_seams_1683e.py::..._wraps_like_any_other_step[masculine]`,
  `test_overlay_size_1107.py` (feet drift 2.5 > 2), `test_overlay_size_review_1107.py` (1798-35+166 > 1920),
  `test_overlay_tumble_1670.py::test_a_curling_throw_turns_against...` (2.45 > 2.75): all read the frames' margins and
  the tumble picture; next step: compare `frame.box`, `_dy("stand")` and the pad of the old and new sets (the crop box
  moved from 263x302 and 263x299 to 262x303 and 263x296) before touching a test.
- Four lints fail on the merge base itself, not on these files: `test_style_scale::test_no_token_is_used_with_a_dead_fallback`,
  `test_global_scope_ratchet`, `test_frontend_wake_sources` (avatars.js raf 7 to 8), `test_module_line_caps` (routes_chat.py).
