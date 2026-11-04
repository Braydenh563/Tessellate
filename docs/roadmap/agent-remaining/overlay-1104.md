# overlay-1104 (agent, port 8828, data /tmp/mm-overlay)

Brief: BACKLOG 16 "Goose-style overlay", rows O1 to O4; INBOX 1645, 1633, 1638.
Nothing here ran on Windows.

## Done

- O1 win32.py + host.py, O2 frames + sprites.py, O3 engine.py, O4 runner.py + wiring (core/desk_companion.py `_sync_overlay`, `_overlay_click`, `panel_corner`, `hide_panel`; desk-companion.js `?overlay=1`; help, Settings popover, manual parity). See git log.
- Frames: 2 looks x 16 frames, 436 KB (limit 1.5 MB), 205x241 and 179x249 px at 2x.
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
