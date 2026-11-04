# overlay-1104 (agent, port 8828, data /tmp/mm-overlay)

Brief: BACKLOG 16 "Goose-style overlay", rows O1 to O4; INBOX 1645, 1633, 1638.
Nothing here ran on Windows.

## Done

- O2 frames: 2 looks x 16 frames, 436 KB total (limit 1.5 MB), 205x241 and 179x249 px at 2x; scripts/render_desk_frames.py + .js, sprites.py, tests/test_overlay_sprites.py.
- O1 win32.py + host.py + tests/test_overlay_host.py + tests/_overlay_fake.py (see git log).

## Next

- O3 engine.py.
- O4 wiring in core/desk_companion.py, __main__.py `_attach_desk_companion`, help, Settings popover, manual parity.

## Unverified (all of it, on Windows)

- Layered window creation, UpdateLayeredWindow draw, click-through of clear pixels, topmost over the taskbar, per-monitor-V2 on the overlay thread, WNDPROC callback lifetime, SHQueryUserNotificationState.
