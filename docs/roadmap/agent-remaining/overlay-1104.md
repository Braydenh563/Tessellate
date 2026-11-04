# overlay-1104 (agent, port 8828, data /tmp/mm-overlay)

Brief: BACKLOG 16 "Goose-style overlay", rows O1 to O4; INBOX 1645, 1633, 1638.
Nothing here ran on Windows.

## Done

- O1 win32.py + host.py, O2 frames + sprites.py, O3 engine.py, O4 runner.py + wiring (core/desk_companion.py `_sync_overlay`, `_overlay_click`, `panel_corner`, `hide_panel`; desk-companion.js `?overlay=1`; help, Settings popover, manual parity). See git log.
- Frames: 2 looks x 16 frames, 436 KB (limit 1.5 MB), 205x241 and 179x249 px at 2x.
- Tests: 152 pass (host 24, sprites 11, engine ~35, runner 11, wiring 12, card window 66 plus the page-API whitelist gained `hide_panel`).

## Remaining

- O5 owner check on Windows: shown, transparent, walks, panel opens, no focus stolen, CPU under 2 percent walking.
- The quick panel stays until Escape, a close button or an action: no click-away dismissal yet.
- A right click when the panel page is still loading (first open) opens the menu, not the settings menu (the event is sent before the page listens).
- A runner thread that dies after a good start is not noticed: the card is not brought back.
- The look is read from the app window once per show (`evaluate_js` with a 1.5 s limit, last look kept); unverified on a hidden WebView2.
- A pet dragged while the panel is open leaves the panel where it was.
- Mixed-DPI panel placement uses the figure's dpi only.

## Unverified (all of it, on Windows)

- Layered window creation, UpdateLayeredWindow draw, click-through of clear pixels, topmost over the taskbar, per-monitor-V2 on the overlay thread, WNDPROC callback lifetime, SHQueryUserNotificationState, the look hand-off, CPU use, the panel taking focus.
