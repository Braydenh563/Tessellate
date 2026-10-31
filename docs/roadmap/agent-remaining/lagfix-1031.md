# lagfix-1031 (the owner's lag reporter, Windows, 2026-10-31)

Branch agent/lagfix-1031, port 8800. Measured with `scratchpad/lag/*.js` probes (scratch, not in the repo): a wrapper on
every layout-forcing read that attributes slow ones to a source line, plus CDP layout and style-recalc counts. The sandbox
ran at load average 30 or more on four cores, so absolute milliseconds swing 3x between runs; call counts, recalc counts
and the forced-read totals are what moved reliably.

## Done

1. avatars.js name-mark buddy: follow loop naps 120ms between reads once the panel held still for three reads (a
   streaming transcript fires the resize observer every frame); transition and animation events from elsewhere on the
   page no longer wake it; `nameMarkBuddyCheck` and `nameMarkBuddyBeat` wait while a chat turn is thinking.
2. phone-shell.js tab press: `revealActiveTab` (shell-reminders.js) skipped when the strip has no fade at either end
   (nothing to scroll into view), and the glide stops asking `getAnimations` (it keeps the one it started).
3. navigation.js `scheduleUpdate` and shell-reminders.js `onScrollEdge`: run in a timer past the frame, not inside it.
5. Settings: `renderAppearance` no longer reads style after its writes (the harmony seed is read a timer past the frame;
   `themeDefaultAccent` is cached on the root's attributes), `settingsIndexWatchSection` builds past the frame.

## Not reproduced or not done

4. graph-canvas.js `gcRequestDraw`: a settled Graph (349 notes, 65 links) draws 0 times in 8s idle, hover ease-out stops
   after 15 draws, back from another tab 0 after 4s. The 51 a second the owner saw matches a layout still cooling at one
   tick per 16ms (each tick is a real move of 1 to 5 screen px even at alpha 0.001), not a loop. An experiment that
   skipped sub-pixel tails changed nothing (the tail is not sub-pixel) and was reverted.
6. editor.js menu row and button mousedown, library.js `openDoc`: not measured.
- `tests/test_lazy_bundle_calls.py` fails on this base (settings-panes.js:1179 `flashRevealedNow`), not from this work.
- `nameMarkBuddyTick` (190 to 281ms) did not fire in an 8s idle window here; its cost is `nameMarkBuddyCheck`'s
  obstacle sweep (one rect and `checkVisibility` per control on the tab), which is still read on every idle tick.
