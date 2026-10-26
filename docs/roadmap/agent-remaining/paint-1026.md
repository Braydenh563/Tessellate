# paint-1026: INBOX 1352, the board, the map and Quick sketch against PaintZ and Ongkon

Source: WHITEBOARD_PLAN "Placed from INBOX, 2026-10-26", item 1352.

## Licences

- PaintZ (`github.com/ZMYaro/paintz`, shallow clone 2026-10-25): no LICENSE file, no licence line in README or package files. All rights reserved by default: ideas only, no code.
- Ongkon (`github.com/uthsobcb/ongkon`): no LICENSE file either. Ideas only.
- Nothing below copies code from either; every build is our own, in our files.

What PaintZ does that we measured against: Shift squares a rectangle or oval and snaps a line to 45 degrees, Ctrl draws from the centre (we use Alt, as our resize already does, decision 40); outline, fill and both; a colour picker and a flood fill; a line-width list with `[` and `]`; one letter per tool in every tooltip; a status bar with canvas size, pointer position and zoom. Ongkon: pen, brush, eraser, three shapes with a fill toggle, a grid, colour picker, size slider, save as JSON or PNG.

## Gap table (measured, 2026-10-25, before any change)

Sweeps: `scratchpad/ui-sweeps/paint1026-audit.js` (board, 1440), `paint1026-sketch.js` (pad, W=1440), `paint1026-map.js` (map, W=960 and 390), `wb1005-format.js` (Format panel, existing).

| # | Surface | Check | Measured before | Impact |
| --- | --- | --- | --- | --- |
| 1 | Board | Shift-drag a rectangle (and triangle, diamond, every library shape) up and left | box x -60 of 120: the square straddles the press point instead of ending at it | high (wrong geometry) |
| 2 | Board | Alt draws a shape from its centre | rect and ellipse with Alt: x 0, y 0 (still from the corner) | high |
| 3 | Board | Shift snaps a line or arrow to 0/45/90 | line to (+120,+14) with Shift: h 14 | medium |
| 4 | Board | Shift straightens a pen stroke | pen with Shift and a 40px bow: h 40 (only the highlighter straightens) | medium |
| 5 | Board, map | The zoom dock says the zoom level (decision 40 counts on it) | zoom dock text "" (three icons, no level) | medium |
| 6 | Board | Format panel properties work (fill, gradient, stroke, width, dash, pattern, rounding, opacity, shadow, ends, font) | `wb1005-format.js` 16/17; the miss is "Right from the last tab wraps", which lands on the fourth (Data) tab the sweep predates | ok |
| 7 | Board | Rail: one size, tooltips with keys | 13 visible, all 36x36, 0 untitled, 0 without a key | ok |
| 8 | Map | One control height in the topic strip | 960: 28 x4, 32 x2 (the two menu buttons); 390: 44 x5, colour well 28x28 | medium |
| 9 | Map | Strip menus open inside the viewport, under 360 wide | 3/3 at 960 and 390 | ok |
| 10 | Pad | Tool tooltips name a key; one letter picks a tool | 0/8 name a key; R does nothing | high (learnability) |
| 11 | Pad | Alt draws from the centre | x -2, y -2 (from the corner) | high |
| 12 | Pad | Ellipse corner to corner | a radius circle 262x262 for a 120x60 drag | high |
| 13 | Pad | Shift line to 45 degrees | h 18 | medium |
| 14 | Pad | Outline, fill and both | no fill at all | high |
| 15 | Pad | Custom colour in the palette | seven fixed swatches only | medium |
| 16 | Pad | Colour picker tool, fill bucket | neither | medium |
| 17 | Pad | Text typed in place | a browser `prompt()` | high (looks broken) |
| 18 | Pad | Status: pointer position, canvas size | none | low |
| 19 | Pad | Download as PNG | none (save as note only) | medium |
| 20 | Pad | `[` and `]` change the size | no | low |
| 21 | Pad | Fit: 1440 card 900 wide, one row, no overflow | pass | ok |

## INBOX 1354 (the owner's second message, ranked first)

1. Interaction feel: handle hit areas, drag threshold, rotate snapping, double-click to edit. Built (below).
2. Popup and context bars stretching to the full width: built (below).
3. Group and Ungroup one state-aware control: measured already one-or-other on the context bar, the right-click menu and Arrange (`paint1026-groups.js`). Kept, now chain-aware.
4. Nested groups. Built (below).
5. Control consistency across the three surfaces. Open (map strip 28/32 heights, gap 8).

## Built

| What | Commit | Sweep, numbers |
| --- | --- | --- |
| Context bar capped at 40rem, fill and text fold last, fold planned from one measurement | 05c9fce | `paint1026-barwidth.js` 27/27 at 1280 and 960, 26/26 at 390 (before 25/27, 25/27, 24/26: line 700, arrow 851 of 1280; rect 2 rows, text 4 rows at 390). Bar open, 20-call mean: 390 line 153 to 51 ms, arrow 114 to 57, rect 77 to 59; 960 arrow 2.0 (unfolded, 776 wide) to 14.5; 1280 arrow 2.0 to 10.6 (it folds now). More menu 304 wide everywhere |
| Feel: 3px click slop (`WB_CLICK_SLOP`, also d3 `clickDistance`), grip hit area by transparent stroke and `::after` (12px mouse, 18px touch), magnetic quarter turns within 3 degrees, up arrow 42 to 56px, phone bar clears the grips, bar fold cached per fill | fcd1cbd | `paint1026-feel.js` at zoom 1: 1280 5/9 to 9/9 (grip reach 5 and 6 to 10 and 11 px, a 2px slip moved it, turn to 88 gave 87 now 90; frames p95 16.7, no long tasks before or after). 390 2/9 to 8/9 (reach 5 and 0 to 12 and 14: the band covered the rotation grip; move p95 50 to 16.7 ms, long tasks 6 to 1; resize 50 to 33, 12 to 2; rotate 50 to 16.7, 11 to 1; CPU profile of a 30-move drag: fold plus bar 945 ms to 0) |
| Nested groups: chain `group_id`, click selects outermost, double-click drills, Ungroup one level, one Undo step each, paste keeps nesting, layers by outermost group | 883fc62 | `paint1026-groups.js` 19/19 at 1280 (before: flat, ungroup of outer cleared all 7, no Undo entry); group walk 0.074 ms per click on 507 items; whole click 7.7 ms, the highlight's (unchanged) |
| Quick sketch rebuilt as a self-contained paint pad (`sketch-pad.js`, `sketch-pad.css`, lazy; markup built by the JS; one host adapter in media.js with standalone fallbacks; `scratchpad/sketch-standalone/`): 13 tools with keys and modifier tips in tooltips, corner/Alt centre/Shift square and 45, outline/fill/both, bucket, picker, inline text, polygon, select and move, 30 undo steps, zoom, status line, paper colour, background picture, Download PNG, Esc cancels in order | (this step) | `paint1026-pad.js` 34/34 in the app at 1440, 720 and 390, 33/33 standalone (gap rows 10 to 20 all closed; before: 0/8 tooltips with keys, ellipse 262x262 for a 120x60 drag, Alt and fill absent, text by `prompt()`). Brush stroke of 120 moves: p95 16.7 ms, no long tasks, at all three widths. Phone: the rail wrapped to two rows (5 tools were past the edge in one scrolling row). Standalone backdrop blur 67 to 17 ms a frame. Boot JS gzip 568,839 to 567,370, boot CSS 178,999 to 178,279; the pad lazy-loads 16.0 + 3.7 KB gzip |

## Remaining

1. Quick sketch: ux-auditor and blind-tester passes, then their fixes.
2. INBOX 1354 item 5: map strip heights 28/32 to one, the phone colour well 28px, the zoom dock shows no zoom level (gap 5).
3. INBOX 1352 board gaps 1 to 4: Shift up-left square ends at the pointer (`wbShapeDims` users), Alt from the centre, Shift lines at 45, Shift pen straight.
