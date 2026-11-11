# settings-1111 (spoke claude/pr216-settings): remaining list

Done: Q10 (stale: Appearance, "Motion at rest" > "Still when idle" already stops the drawn loops 2 s after input; tests/test_companion_rest_w14.py), Q30 (stale: Settings "New notes start private", off by default, private spaces seal on the way in; tests/test_private_by_default_1695.py).
Done: Q11 probe (commit 1).
Next: Q25 Settings row + first-run preferences step; item 1 notices (blocked: extra-notice.js and pkg-1111.md not in origin); W20; W33.
Pre-existing red at ee75195: tests/test_codeql_shapes.py::test_no_new_request_inside_an_assert (228 vs cap 226; test_prose_autofill.py 1, test_state_machines_1747.py 2), tests/test_atlas_frame_reads.py::test_a_walking_rig_stops_reading_style_once_its_arms_hold_still.
