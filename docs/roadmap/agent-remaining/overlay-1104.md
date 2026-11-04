# overlay-1104 (agent, port 8828, data /tmp/mm-overlay)

Brief: BACKLOG 16 "Goose-style overlay", rows O1 to O4; INBOX 1645, 1633, 1638.
Nothing here ran on Windows.

## Done

- O1 win32.py + host.py, O2 frames + sprites.py, O3 engine.py, O4 runner.py + wiring (core/desk_companion.py `_sync_overlay`, `_overlay_click`, `panel_corner`, `hide_panel`; desk-companion.js `?overlay=1`; help, Settings popover, manual parity). See git log.
- Frames: 2 looks x 18 frames (adds hang, tumble), 284 KB (limit 1.5 MB), 226x291 and 230x295 px at 2x. Re-rendered solid (opaque share 84 percent, was 14 to 29), eyes with pupils, no aura; Atlas walk0 to walk5 are a float cycle (bob, lean, tail wave).
- Tests: 152 pass (host 24, sprites 11, engine ~35, runner 11, wiring 12, card window 66 plus the page-API whitelist gained `hide_panel`).

## Built since (unverified on Windows, tests through the fakes only)

- Click-away: the panel page reports a blur (armed after its first focus) to `panel_blur`; a left click within `BLUR_GRACE` of that is the press that blurred it and does not reopen.
- A thread that ends without `stop` calls `OverlayHost.on_exit`, then the runner's `on_died`, then the card window replaces the overlay (no polling).
- A drop while the panel is open re-places it through `panel_corner` (figure size and dpi from the last click).
- First-open right click: Python holds the intended menu, the page asks `panel_kind` once its API is ready.

## Remaining

- O5 owner check on Windows: shown, transparent, walks, panel opens, no focus stolen, CPU under 2 percent walking.
- The look is read from the app window once per show (`evaluate_js` with a 1.5 s limit, last look kept); unverified on a hidden WebView2.
- Mixed-DPI panel placement uses the figure's dpi only.

## Unverified (all of it, on Windows)

- Layered window creation, UpdateLayeredWindow draw, click-through of clear pixels, topmost over the taskbar, per-monitor-V2 on the overlay thread, WNDPROC callback lifetime, SHQueryUserNotificationState, the look hand-off, CPU use, the panel taking focus.

## Owner reports 2026-11-04 (first run on Windows)

- (a) "it isnt animated and it's creepy", (b) "doesnt move ... no physics". Cause: the runner set `reduced` from the Windows animation flag alone, and the reduced state shows only the "sit" frame, never walks or falls. Fix: the overlay follows the app's resolved Companion movement (`nameMarkBuddyMotion`), read with the look in one `evaluate_js` (`LOOK_SCRIPT`, bounded by `LOOK_WAIT`); no answer falls back to the Windows flag; a change restarts the runner where it stood; the log line names the mode and reason. A still figure's right-click menu says why and offers Let it walk (sets `avatar-buddy-motion` to always, restarts moving; not offered when Avatar animation is off). A still drop lands on the floor at once (`engine._release`), so it never hangs in mid-air. The moving path was walked (host `_event` to `_set_timer` to `_on_timer`): it does ask for ticks after show and for a fall after a mid-air drop; tests drive that with fake time. Unverified: the look of the frames in motion, and whether a hidden WebView2 answers the script inside 1.5 s (if not, the Windows flag decides).
- (c) right-click flash and scrollbar. Cause: the panel window was made and shown at the quick menu's size, then resized by the page to a fixed context height (108) too small for two rows at the owner's scale. Fix: Python sizes the window for the click that opens it (`PANEL_SIZES`) before it is shown, clears the page on hide (`desk-close`) so the next open does not flash the last menu, and the page asks for the menu's measured height (`menuHeight`). Unverified: the exact rows' pixel height at 125 to 200 percent scale, and that a freshly made window shows no blank card while the page loads.
- (d) Settings hides the panel and the app opens 5 to 10 seconds later by hand. Cause (by reading, not reproduced): `_open_main` only called `show` and focus, which leaves a minimised window minimised, and the page hid the panel before asking, which can lose the foreground right; the settings script then waited in `evaluate_js` on a window that was not drawn until the person opened it. Fix: `_bring_forward` (restore, show, focus, as a second launch does), the page opens first and hides the panel after, the script runs on a worker (`desk-open-script`), so no click waits on it; tested with a blocking `evaluate_js` under 0.5 s. Unverified on Windows: that SetForegroundWindow is now granted, and the real wait.
