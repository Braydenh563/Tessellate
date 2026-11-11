# settings-1111 (spoke claude/pr216-settings): remaining list

Done: Q10 (stale: Appearance, "Motion at rest" > "Still when idle" already stops the drawn loops 2 s after input; tests/test_companion_rest_w14.py), Q30 (stale: Settings "New notes start private", off by default, private spaces seal on the way in; tests/test_private_by_default_1695.py).
Done: Q11 probe 94cff43; Q25 2539670 (before: setting, date order, welcome preferences card); item 1 (Q27 notices on nine features, RapidOCR card 140 MB) e935fdc, details in pkg-1111.md.
Done: W20 (C19, C22 built earlier; C20, C21, C23 not reproduced, numbers in OPEN.md); W33 (E12 waits on the owner, E13 no repro, E14 deliberately empty; s8-1110.md).
Left: nothing assigned. Not verified: a real install through the notice's Install button (fake transport).
Red not from this branch: tests/test_global_scope_ratchet.py (9046 names, cap 9044, already so on origin/claude/next-queue-1102 3d08f4e4d), tests/test_codeql_shapes.py (228 vs 226 at ee75195, absent after the merge), tests/test_atlas_frame_reads.py::test_a_walking_rig_stops_reading_style_once_its_arms_hold_still (at base).
