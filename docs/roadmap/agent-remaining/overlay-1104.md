# overlay-1104 (agent, port 8828, data /tmp/mm-overlay)

Brief: BACKLOG 16 "Goose-style overlay", rows O1 to O4; INBOX 1645, 1633, 1638.
Nothing here ran on Windows.

## Done

- O1 win32.py + host.py + tests/test_overlay_host.py + tests/_overlay_fake.py (see git log).

## Next

- O2 frames: scripts/render_desk_frames.js (node, Playwright from the app page), core/overlay/sprites.py.
- O3 engine.py.
- O4 wiring in core/desk_companion.py, __main__.py `_attach_desk_companion`, help, Settings popover, manual parity.

## Unverified (all of it, on Windows)

- Layered window creation, UpdateLayeredWindow draw, click-through of clear pixels, topmost over the taskbar, per-monitor-V2 on the overlay thread, WNDPROC callback lifetime, SHQueryUserNotificationState.
