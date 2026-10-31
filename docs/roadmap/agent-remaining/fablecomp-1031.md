# fablecomp-1031 (INBOX 1463, companion upgrade): remaining

Branch agent/fablecomp-1031, port 8831, data /tmp/claude-0/fablecomp-data. Probes in the session scratchpad `fc/` (not in the repo): enterprobe.js (entrances), tickcost.js and sweepparts.js (obstacle cost at 4x CPU).

## Done

- Step 1, quiet page changes: `nameMarkBuddyQuietEnter` (fade 180ms or 28px of steps), `nmb.quiet` crossfade for a sub-view's far move, Settings Showy entrances (`avatar-buddy-showy`, pref `avatar-buddy-entrances`). tests/test_companion_quiet_1463.py.
- Step 2, obstacle cost: `nameMarkBuddyNear` filters a kept sweep (`nameMarkBuddyControlBoxes`, `nmb.covers`, reset on scroll, resize, tab mutation, 15s); popups by id, class and tag (`NMB_POPUP_IDS`, `NMB_POPUP_CLASSES`). Warm check at 4x CPU 34.9/69.5/36.7/62.3 to 0.1/0.1/1.0/1.5ms (notes, library, chat, dashboard). tests/test_companion_near_1465.py. Commit 0ebe46c.
- Step 3, behaviour model: `nameMarkBuddyStateOf`/`nameMarkBuddyState` (`data-state`), `nameMarkBuddyAttention` and `nameMarkBuddyCaret` in Obstacles and Dodge, `nameMarkBuddyRoomSoon`/`nameMarkBuddyRoom`, `NMB_TRAITS`, far wander after 60s idle. tests/test_companion_state_1463.py.

## Next

4. Micro-detail: state transitions, idle variety, reduced motion.
5. Help and DESIGN.md row.

## Found, not fixed

- tests/test_complexity.py fails as merged from the working branch (composer_digest, composer_lists, composer_study, agent.run_agent over 15; the lazy import cycle at two groups); none of these files is touched here.
