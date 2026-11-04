# Companion 1663: what is left

Done: frames re-rendered uncut (capture box 400x300, figure pinned each frame), drawn-box panel placement, still hang, float band.

- Not verified on Windows: the panel gap and the end-to-end look of the new frames in a real layered window (all tests use the fake `win32`); log `Output` x/y and the panel box against `GetWindowRect` and the work area on a real mixed-dpi desktop.
- "Popup moves left or right and is cut vertically": left/right swing was the mirror-dependent margin (now placed from the drawn box); a vertical cut was never reproduced (`desk_companion.panel_placement` clamps inside the work area). Confirm on Windows.
- Float bob (`BOB` 7 px) and sway (`FLOAT_SWAY` 5 px) are kept; cut them if the owner still finds the float restless (`engine.py` near line 126).
- The frame renderer's nebula pass is flaky: one run in three left two frames with almost no stream (`tests/test_overlay_sprites.py::test_the_nebula_stream_is_in_every_frame_soft_but_visible` catches it; re-run `scripts/render_desk_frames.py`). Cause not found (`render_desk_frames.js`, the second screenshot pass).
- `tests/test_overlay_roam_runner.py::test_window_tops_are_read_at_most_once_a_second_and_given_to_the_engine` fails under `-n 3` load and passes alone (timing, not this change).
