# dgsel-1111 remaining (INBOX 1740)

Done: picture picks like the whiteboard (diagram-canvas.js marquee on plain mouse drag, Shift/Ctrl adds; diagram-multi.js `S.pickAt` toggles for Shift/Ctrl+click; Ctrl+arrows extend; Space+drag and middle button pan in diagram-view.js).

- Verified 1111 (Chromium, 8915): Space+drag at zoom 1.35 sets `.dgm-hand` and cursor grab, scrollTop 73 to 145 (clamped); middle-button drag scrollTop 145 to 20; hand class off after release. Touch emulation at 390 (hasTouch, isMobile): one-finger pan scrollTop 81 to 203, long press (1 s) on a box opens its Block menu. The drive found the list lying over the picture at 390 (fixed, see dgfold).
- Found, not fixed: at 390 a long press on a box under the picked box's connect handles hits the handle, not the box (the handles overlap the neighbour).
- Not verified: Cmd+arrows on macOS (the OS may take Ctrl+arrows for Spaces).
- Sequence/mind-map/timeline panes (S.k) keep their own gestures; the marquee is flowchart only.
