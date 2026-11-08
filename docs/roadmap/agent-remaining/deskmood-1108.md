# deskmood-1108 remaining

- done: sad when left alone (`engine.LONELY_AFTER` 900 s, between `IDLE_SIT` 600 and `IDLE_SLEEP` 1200; `Engine._lonely`, reuses `refused`), `idle_return` emitted (`screenwatch.input_seen`, `AWAY_AFTER` 600 s, answered from `runner._read_typing`), confused on a missed drop (`Engine._missed`, reuses `confused`). Tests: `tests/test_overlay_mood_1108.py`, one runner test in `tests/test_overlay_runner.py`.
- left: a missed THROW is not covered (a throw does not aim at a window top; only the slow-release drop that `_top_in_reach` notes as out of reach counts). Say if a throw that ends on the floor under a window should also look confused.
- left: `idle_return` needs input age from the backend (`last_input_age`): Windows and X11 only; real input rates and the 0.5 Hz typing-check latency unverified on a real desktop.
- left: the sad look uses the plain face over a sit or stand (no sad act or lower-body pose; the desk `lower.sad` row is C4, desklayers).
- left: wider overlay suite (all `tests/test_overlay*.py`) was not completed here (machine busy, run killed by load); only the files named in the CHANGELOG lines plus runner, shake, landing and catalogue tests ran green.
