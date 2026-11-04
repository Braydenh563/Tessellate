# desk-live-1670 remaining (agent, from the owner's live Windows reports 12:17Z to 12:20Z)

Done: busy notification state no longer hides the figure (`win32.QUNS_HIDE`); bob 4 px at 0.22 Hz, BOB_TICK 0.125; frames re-rendered (pose, mood and perch held, stream pinned and shared, steady screenshots); floater thrown down lands (`engine._do_fly`); in-app hang pose dropped on pick-up (`avatars.js` nameMarkBuddyHalt). Tests: tests/test_overlay_bob_1670.py, tests/test_overlay_hang_throw_1670.py, test_overlay_runner busy test.

Not verified: real Windows (the QUNS values, DWM, the drawn bob); the in-app pose fix is a source test plus one Playwright probe, not a full throw sweep.

Found, not fixed:
- "it crossed my screen completely and chilled in the middle" (INBOX 1670 12:17Z): roaming, left to the roaming row (engine.py float legs, FLOAT_LEG).
- The in-app companion still lands on a hang spot (an under-bar edge) when thrown down near the top bar; that is a real hang, not the stuck pose.
- `scripts/render_desk_frames.js` frames 2 to 5 of the idle cycle can still catch the page's own WAAPI eyes mid-blink; check `r.py`-style per-frame solid and centroid after any re-render.
