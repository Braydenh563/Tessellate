# sketchfix-1026: Quick sketch review findings

Independent reviews of the paint-1026 Quick sketch (ux-auditor, blind-tester),
run on 8eaa506. Code: `frontend/js/sketch-pad.js`, `frontend/css/sketch-pad.css`,
`openSketch` and `sketchHost` in `frontend/js/media.js`, standalone page
`tools/sketch-standalone/`. Sweeps: `scratchpad/ui-sweeps/paint1026-pad.js`,
`paint1026-pad-a11y.js` (a check per fix, marked "fix N").

## Done (agent/sketchfix-1026)

Measured by the two sweeps at 1440x900, 720x900 and 390x844, light and dark,
in the app and on the standalone page.

- [x] 1. Rail at 720x900: two columns per group from 600 to 819 wide, under
  800 tall and on a coarse pointer. scrollHeight 662 vs 558 to 611 vs 611.
- [x] 2. `#sketch-card { margin: 0 }`: card y -8 to 0 at 390.
- [x] 3. `[ ] + = - 0` sit behind `host.singleKeys()` with the tool letters.
- [x] 4. Forced colours: `forced-color-adjust: none` on swatches and wells
  (12 distinct colours, was 1), a 3px Highlight outline on the one that is on.
- [x] 5. Swatches 24 to 28 (44 under 820), wells 32 to 44 tall under 820,
  caption 32 to 44 under 820; no target under the floor at any width.
- [x] 6. Not reproduced: 0 of 7 fresh logins (720 and 390, two fresh data
  dirs and the sweep dir, sampled every 250ms from the unlock): the Quick
  access row and its Sketch tile were drawn before or within 260ms of the
  lock lifting every time. Nothing changed outside the pad.
- [x] 7. Phone: palette, size and style under one "Colour, size and style"
  popover; rail two rows (153 to 100); foot one row (94 to 44, Download as a
  glyph). Viewport 222 to 497px, 26% to 59% of 844.
- [x] 8. Keys whose target is outside the pad (the confirm, the help popover)
  are left alone: `b` and `]` under the confirm change nothing.
- [x] 9. Roving tabindex in the rail and each bar group: Tab stops 45 to 13
  (10 at 820 and under with the popover shut); arrows, Home and End.
- [x] 10. `.sp-swatch` `aria-pressed`, set in `paintWells`.
- [x] 11. Save is `aria-disabled` until something is drawn; a press says
  "Draw something first." and posts nothing.
- [x] 12. A failed save: the message in `--error`, the app's error toast,
  Save still offered; the message moved to the fixed-height status row, so
  the viewport rect is identical before and after.
- [x] 13. Escape while typing places the text.
- [x] 14. Close confirm: "Discard sketch" and "Keep drawing".
- [x] 15. Standalone menu clamped to the window (8px gutter), Up, Down, Home
  and End walk it.
- [x] 16. Zoom button named "Zoom 54%, show at 100%" / "Zoom 100%, fit the page".
- [x] 17. Help: keys in two columns, one line per area; 548 in 510 (scrolls)
  to 488 (no scroll). Clear and Download left the More menu. `.sp-status`
  37 to 44 under 820.
- [x] 18. Slider named "Text size" with the Text tool; the editor is clamped
  to the page (`wrap=off`, max width and height): overhang 830 to 0.
- [x] 19. Ctrl+Shift+Z redid in every run (focus on the page or a tool); a
  check now holds it. Initial focus is the page (the viewport, now a Tab
  stop), not the Pencil.

Also (CI on PR 204): the pad's snapshot stack is `snapshotInk` (not the app's
`pushUndo` name), its default prefs are in memory with localStorage moved to
the standalone `boot.js`, the Download hover has its focus twin, and the
wake-source seed holds sketch-pad.js at 2 rafs (the status readout, the text
box's focus after the press) and 1 ResizeObserver (the viewport refit); the
open's frame wait was dropped.

## Remaining

None.
