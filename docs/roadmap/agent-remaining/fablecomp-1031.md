# fablecomp-1031 (INBOX 1463, companion upgrade): remaining

Branch agent/fablecomp-1031, port 8831, data /tmp/claude-0/fablecomp-data. Probes in the session scratchpad `fc/` (not in the repo): enterprobe.js (entrances), tickcost.js and sweepparts.js (obstacle cost at 4x CPU).

## Done

- Step 1, quiet page changes: `nameMarkBuddyQuietEnter` (fade 180ms or 28px of steps), `nmb.quiet` crossfade for a sub-view's far move, Settings Showy entrances (`avatar-buddy-showy`, pref `avatar-buddy-entrances`). tests/test_companion_quiet_1463.py.
- Step 2, obstacle cost: `nameMarkBuddyNear` filters a kept sweep (`nameMarkBuddyControlBoxes`, `nmb.covers`, reset on scroll, resize, tab mutation, 15s); popups by id, class and tag (`NMB_POPUP_IDS`, `NMB_POPUP_CLASSES`). Warm check at 4x CPU 34.9/69.5/36.7/62.3 to 0.1/0.1/1.0/1.5ms (notes, library, chat, dashboard). tests/test_companion_near_1465.py. Commit 0ebe46c.
- Step 3, behaviour model: `nameMarkBuddyStateOf`/`nameMarkBuddyState` (`data-state`), `nameMarkBuddyAttention` and `nameMarkBuddyCaret` in Obstacles and Dodge, `nameMarkBuddyRoomSoon`/`nameMarkBuddyRoom`, `NMB_TRAITS`, far wander after 60s idle. tests/test_companion_state_1463.py. Commit e4db1f7.
- Step 4, beats: `NMB_SETTLES`, `NMB_BEAT_MS`, `nameMarkBuddySettleKind`, `nameMarkBuddySettleIn` (never the same twice, `composite: add`, none when still), `nameMarkBuddyGlanceAtPage` after a quiet way in or a view change it stays through. Reduced motion measured: 0px travel, no beat, no glance. tests/test_companion_beats_1463.py. Commit 64360b1.
- Step 5, help: the companion-travel Guide topic carries the quiet arrivals, keeping clear of the caret and focused control, making room, traits and beats (the companion topic sits at its reply budget, 1,881 of 1,900); DESIGN.md's companion recipe row names the one model and the popup lists.

## Next

Nothing left of the brief. Not verified: the owner's Windows webview, the GPU compositing of the beats, behaviour with a real model running.

## Found, not fixed

- Reset appearance (`resetAppearance`, settings.js) leaves `avatar-buddy-motion` and `avatar-buddy-entrances` as they were.
- tests/test_complexity.py fails as merged from the working branch (composer_digest, composer_lists, composer_study, agent.run_agent over 15; the lazy import cycle at two groups); none of these files is touched here.
