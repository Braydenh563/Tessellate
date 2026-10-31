# fablecomp-1031 (INBOX 1463, companion upgrade): remaining

Branch agent/fablecomp-1031, port 8831, data /tmp/claude-0/fablecomp-data. Probes in the session scratchpad `fc/` (not in the repo): enterprobe.js (entrances), tickcost.js and sweepparts.js (obstacle cost at 4x CPU).

## Done

- Step 1, quiet page changes: `nameMarkBuddyQuietEnter` (fade 180ms or 28px of steps), `nmb.quiet` crossfade for a sub-view's far move, Settings Showy entrances (`avatar-buddy-showy`, pref `avatar-buddy-entrances`). tests/test_companion_quiet_1463.py.

- Step 2, obstacle cost: `nameMarkBuddyNear` filters a kept sweep (`nameMarkBuddyControlBoxes`, `nmbCovers`, reset on scroll, resize, tab mutation, 15s); popups by id, class and tag (`NMB_POPUP_IDS`, `NMB_POPUP_CLASSES`). Warm check at 4x CPU 34.9/69.5/36.7/62.3 to 0.1/0.1/1.0/1.5ms (notes, library, chat, dashboard). tests/test_companion_near_1465.py.

## Next

3. Behaviour model: explicit state, focus and caret as obstacles, making room for the pointer, traits.
4. Micro-detail: state transitions, idle variety, reduced motion.
5. Help and DESIGN.md row.
