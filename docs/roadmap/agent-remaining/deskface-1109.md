# deskface-1109 remaining

Done: the INBOX 1704 commit (faces, blink, flow, stretch cap); the INBOX resolution follows it in `git log`.

- Not verified on a real Windows desktop: everything is measured on the shipped frames at 96 and 192 dpi and on the engine with a fixed clock; nothing ran against a real overlay window or a real display.
- Found, not fixed (art): `scripts/render_desk_frames.py` `clip_idle_tails` pins the feminine stand, blink, look and idle7 to idle16 tails to one lowest row, so the shipped tail ends in a flat cut (36 to 45 px solid in the last row; masculine idle13 15 px). `sprites.tapered` now fades the last 8 rows at load; the real fix is to stop the clip cutting solid pixels (re-render with the tail tip kept) and drop `tapered`.
- Found, not fixed: the blink phases cost wakes (`tests/test_overlay_engine.py` standing budget is 392, now 386 of 60 s). A smoother blink (four phases) needs the flow tick folded into the same wake, `engine._flash_due` and `_wake_at_rest`.
- Found, not fixed: a captured companion (no charted eye box) has no face layer, so its blink shows the open picture for the first and last 30% of the 0.28 s and the shipped shut picture between; it was a plain 0.18 s pop before.
- Joy, laughing and love tint a faint lighter disc round each eye (the skin patch is sampled between the eyes); feathered now, not matched to the local shading: `faces._cover`.
