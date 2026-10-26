# sketchfix-1026: Quick sketch review findings

Independent reviews of the paint-1026 Quick sketch (ux-auditor, blind-tester),
run on 8eaa506. Code: `frontend/js/sketch-pad.js`, `frontend/css/sketch-pad.css`,
`openSketch` and `sketchHost` in `frontend/js/media.js`, standalone page
`tools/sketch-standalone/`. Sweeps: `scratchpad/ui-sweeps/paint1026-pad.js`,
`paint1026-pad-a11y.js` (extend them for each fix).

## Remaining

High
1. `.sp-rail` at 720x900: scrollHeight 662 vs clientHeight 558; Fill and
   Colour picker hidden, no scroll cue. Wrap to two columns or use the row
   layout below about 900px tall.
2. `#sketch-card` at 390x844: y -8 (inherits `.card` margin-bottom 16px);
   head clipped 8px. `#sketch-card { margin: 0 }`.
3. `[ ] + = - 0` act with single-key shortcuts off (`PLAIN`, about line
   1306); WCAG 2.1.4. Check `S.host.singleKeys()` first.
4. Forced colours: swatches and wells all white, active ring `box-shadow:
   none`. `forced-color-adjust: none` on swatches and wells, an outline
   for the active one.
5. Targets: `.sp-swatch` 24x24, `.sp-custom` 26x32 at 1440, `.sp-caption`
   32 tall under 820. DESIGN floor 28, 44 under 820 or coarse pointer.
6. Dashboard blank after a fresh login at 720 and 390 (no Quick access
   row, no Sketch tile) until a tab switch; 3 of 3 runs. Not the pad;
   reproduce first.

Medium
7. Phone 390: controls take 555px, canvas 330x206 at 34%. Fold palette,
   size and style into one popover and the foot into the bar; target a
   viewport of at least 50% of the height.
8. Keys leak past the close confirm: `b` changes tool behind the dialog
   (capture listener about line 1488). Return early when `e.target` is
   outside `S.root`.
9. Toolbars: 45 tab stops; `role=toolbar` without arrow keys. Roving
   tabindex in the rail and each bar group.
10. `.sp-swatch` has no `aria-pressed`; set it in `paintWells`.
11. Save on a blank page writes an empty "Sketch: date" note. Disable Save
    until dirty, or say "Draw something first".
12. A failed save shows the server message in muted text only. Error token
    plus the app's error toast; Save still offered. Offline status reflows
    the footer and moves the canvas: reserve its height.
13. Esc while typing text discards it silently; Esc commits the text.

Low
14. Close confirm says "Cancel"/"OK": pass `confirmLabel: "Discard sketch"`
    through `sketchHost().confirm`.
15. Standalone `.sp-menu` at 390: x -7; clamp to the viewport; arrow keys
    in `fallbackMenu`.
16. `[data-sp=zoom]` accessible name is "100%": `aria-label` "Zoom 100%,
    fit the page", updated in `applyZoom`.
17. Help `#sketch-help` scrolls (548 vs 510): one line per area (wells,
    shape style, paper, Add a picture); drop the duplicate Clear and
    Download menu rows. `.sp-status` 37px tall holding 44px buttons:
    `min-height: var(--target-min)`.
18. Text size follows the stroke slider (24 makes huge text; the editor
    box overhangs the page by about 830px). Label the slider as text size
    for the Text tool, and clamp the editor to the page.
19. Ctrl+Shift+Z does not redo. Initial focus is the Pencil; put it on the
    canvas or first bar control.
</content>
</invoke>
