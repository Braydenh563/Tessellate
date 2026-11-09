# cispeed-1109 remaining (CI Tests jobs near the 60-minute cap)

- Done: engine hot paths (tail and flow springs, grid-cell look-aheads, act look-ahead), shared seeded hour, shared frame boxes in `make()`. Output for a fixed seed is identical (state, act, x, y, wake, frame, pose hashed over 13 seeded 1 to 2 hour runs, before and after).
- Overlay top-15 CPU (10 files, three shards): 710 s before, 401 s after. Biggest left: `test_overlay_rest_1670.py::test_a_hang_is_long...` 81 s (46 simulated hours), `test_overlay_life_1670.py::test_micro_things...` 69 s (60 simulated hours).
- Next: the remaining cost is Engine.update itself (about 85 us per 300 ms act wake): `behaviour.py` `FlowField.step` (n=15 sub-steps x 14 springs, 1 s per 70k wakes) and `engine.py` `_next_act_pose_change` (30 samples per wake). A closed-form rest for a settled flow (all pos and vel exactly zero) would be bit-identical.
- Not covered: tests outside the overlay files (`test_launcher_scripts` 20 s, `test_resurface_spec` 18 s, `test_search_engine_spec` setups 15 s, `test_backup_roundtrip_full` 13 s) were not touched.
- Not verified: the full CI run on 4-core runners; the numbers are process CPU seconds on a loaded shared box.
