# fablecomp-1031 (INBOX 1463, companion upgrade): remaining

Branch agent/fablecomp-1031, port 8831, data /tmp/claude-0/fablecomp-data. Probes in the session scratchpad `fc/` (not in the repo): enterprobe.js (entrances), tickcost.js and sweepparts.js (obstacle cost at 4x CPU).

## Done

- Step 1, quiet page changes: `nameMarkBuddyQuietEnter` (fade 180ms or 28px of steps), `nmb.quiet` crossfade for a sub-view's far move, Settings Showy entrances (`avatar-buddy-showy`, pref `avatar-buddy-entrances`). tests/test_companion_quiet_1463.py.

## Next

2. Obstacle cost: hit tests near its shape (`nameMarkBuddyNear`), avatars.js `nameMarkBuddyCheck` ~6640, `nameMarkBuddyObstacles` ~3676. Before (4x CPU, tickcost.js): obstacles 27.7 notes, 39.1 library, 26.6 chat, 31.1 dashboard ms; check 26.0, 41.2, 20.9, 32.1.
3. Behaviour model: explicit state, focus and caret as obstacles, making room for the pointer, traits.
4. Micro-detail: state transitions, idle variety, reduced motion.
5. Help and DESIGN.md row.
