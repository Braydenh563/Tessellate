# desklayers-1108 remaining

- done C1 (tail layer): `behaviour.TailLayer`, `sprites.SpriteSet.tailed`, `runner._new_picture`; test `tests/test_overlay_tail_layer_1108.py`.
- next C4 (lower layer): `behaviour.FLOW_LOWER`, `engine._lower_state`; test `tests/test_overlay_lower_layer_1108.py`.
- left: real Windows rendering of the tail warp and the 30 a second pace unverified (FakeWin32 and Pillow only); the warp shears the baked tail (columns of the tail's region moved by the eased control points), it does not redraw a rig tail, so a pose reads as a bend, not a loop; `tail.hook`, `coil_hold`, `thump`, `shiver`, `loop8`, `tip_twitch`, `balance`, `pillow`, `tuck` (C2, C3) are new poses to add to `TAIL_POSES`.
- left: the layer is on for stand and sit of a floater only (`behaviour.TAIL_FRAMES`); walk, sleep, act and hang frames keep their baked tail.
- note: owner call, CPU: 30 tail ticks a second cost about 4 percent of a core at dpi 192 (a tick is the tail warp, 1.3 ms); `TAIL_LAYER_MS` 66 halves it. The rest wake bars in `test_overlay_rest_1670.py` and `test_overlay_parity_1683.py` now bound at that pace.
- found, not fixed: `tests/test_companion_catalogue_1108.py::test_every_table_row_is_catalogued[desk]` fails on the base (6 desk `react:` rows have no catalogue entry); `test_overlay_pace_1683.py::test_an_act_wakes_at_the_frame_its_pose_steps...` and `test_overlay_slow_tick_1108.py::...[4-walk]` fail on the base too.
