# dgsel-1111 remaining (INBOX 1740)

Done: picture picks like the whiteboard (diagram-canvas.js marquee on plain mouse drag, Shift/Ctrl adds; diagram-multi.js `S.pickAt` toggles for Shift/Ctrl+click; Ctrl+arrows extend; Space+drag and middle button pan in diagram-view.js).

- Not verified: touch long-press and one-finger pan in a real touch browser (tests/test_diagram_touch.py passes; canvas skips `pointerType === "touch"`).
- Not verified: Space+drag and middle-button pan driven in Chromium (code read only; check `.dgm-hand` cursor and a zoomed pan).
- Not verified: Cmd+arrows on macOS (the OS may take Ctrl+arrows for Spaces).
- Sequence/mind-map/timeline panes (S.k) keep their own gestures; the marquee is flowchart only.
