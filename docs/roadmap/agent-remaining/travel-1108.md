# travel-1108: "Go somewhere else" (INBOX 1696 i, repeat report)

Log:
- Engine at head, 72 random-state wander trials (2 looks, 2 gaits, seeds 1 to 6) plus 64 fixed-stand trials: seen move or walk frames, facing the goal, arrived, no return to the old spot. The earlier fix (4175966f) holds; the engine path is not the cause.
- Reproduced at a draw rate under 10 a second (the owner's screen drew at about 8, INBOX 1696 a): `_pace` counted any tick more than `PACE_GAP` (0.1 s) after the last as a fresh start, so every tick restarted the ease-in. A 900 px run went at 5 px/s (measured 900 to 507 in 48 s at 0.1 s ticks with float rounding, 900 to 102 in 148 s at 0.12 s); the walk cycle follows distance, so no visible change. Fix: `PACE_GAP` 0.4. Test `tests/test_overlay_slow_tick_1108.py` (fails before: 3 of 3 ticks; 15 pass after).
- The in-app companion command (`frontend/js/companion-travel.js`) is a separate path (avatars.js) with no "go somewhere else" row; not changed.

Left:
- "Poofed back" itself was not reproduced; the slow crawl leaves a long trip open to timers, which is the best reading. Needs a real Windows desktop at 200% scale to confirm.
- A hitch tick still moves the world by at most `MAX_DT` (0.1 s), so a figure drawn at 8 a second travels about 80% of its speed (engine.py `update`). Not changed.
- The Windows overlay's frame rate on a 2560x1504 screen at 200% (INBOX 1696 a) is the deeper cause of the slow draw; unmeasured here.
- The saved position pref (`OVERLAY_POS_PREF`) is written only on a drop (`_overlay_settle`), so a runner restart after a wander restarts the engine at its current place but forgets the goal (desk_companion.py `_runner_place`); a trip in flight stops there. Not verified on Windows.
