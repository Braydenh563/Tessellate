# compclip-1031 (INBOX 1463, 15:25 report)

- Cause: `duck` far move in frontend/js/companion-travel.js hid it behind a bar with an animated clip-path and re-entered from the opposite bar (bottom to top wrap).
- Done: duck removed (chooser, player, constants); tests/test_companion_never_clipped_1463.py; test_companion_travel.py follows.
- Probe: scratchpad compclip-probe.js (not in repo), before 453/6639 clipped, 312 below the status bar's top (1440); after 0 clipped of 2,329 frames and 0 below at 1440, 0 of 2,285 at 390 (probe frame counts differ because the duck rows are gone).
- Left: nothing known. Not verified: the owner's Windows webview; a GPU seam inside Atlas's layers.
- Gate (--staged) on this commit: two red lints that are not from this change: tests/test_lazy_bundle_calls.py (settings-panes.js:1179 flashRevealedNow, 'reveal' bundle) and tests/test_plan_hygiene.py::test_inbox_is_a_tray_not_a_backlog (INBOX at 20 items).
