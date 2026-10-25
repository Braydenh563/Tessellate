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

1. Interaction feel: handle hit areas, drag threshold, rotate snapping, double-click to edit. Open.
2. Popup and context bars stretching to the full width: cap, fold into "...". Open.
3. Group and Ungroup one state-aware control: measured already one-or-other on the context bar, the right-click menu and Arrange (`paint1026-groups.js`). Kept, now chain-aware.
4. Nested groups. Built (below).
5. Control consistency across the three surfaces. Open (map strip 28/32 heights, gap 8).

## Built

| What | Commit | Sweep, numbers |
| --- | --- | --- |
| Nested groups: chain `group_id`, click selects outermost, double-click drills, Ungroup one level, one Undo step each, paste keeps nesting, layers by outermost group | (this step) | `paint1026-groups.js` 19/19 at 1280 (before: flat, ungroup of outer cleared all 7, no Undo entry); group walk 0.074 ms per click on 507 items; whole click 7.7 ms, the highlight's (unchanged) |

## Remaining

(written before stopping)
