# wbdog-1026: whiteboard dogfood (INBOX 1358)

Scripts live in the session scratchpad (`wbdog/`), not the repo. Student story at 1440x900 and 390x844, light and dark; 23 driven scripts (d1 to d23), about 60 checks.

## Done (class, fix, test)
- **Selection by first match**: Format panel Bold and Italic wrapped the first occurrence of the words, not the selected ones; now by offsets, a second press unwraps (`wbWrapRange`, tests/test_wb_wrap_range.py).
- **Ghost selection**: an undone paste left ids in `wbMultiSelection`, so Export > Selection threw; `wbPruneSelection` runs first in every render (tests/test_wb_prune_selection.py).
- **Text hidden behind a scroll bar**: a text box or sticky grew only on blur; now grows as you type (`wbGrowBoxToWords`, tests/test_wb_grow_box.py).
- **Words overflowing a shape**: a label longer than the shape spilled out; the shape grows in proportion until it fits (`wbGrowShapeToLabel`, tests/test_wb_grow_shape.py).
- **Find and Replace skipped table cells**: "0 matches" for a word inside a table; cells are searched and replaced, one undo (tests/test_wb_find_cells.py).
- **No keyboard-only path** (WCAG 2.1.1): N, Enter did nothing and a selected sticky needed a double-click; `wbKeyboardEnter` places the held tool at the view centre and edits a lone text box (tests/test_wb_keyboard_enter.py, Keys sheet row, Guide topic board-keyboard-create).
- **Export drew boxes as words** (in progress, see below).

## Found, not fixed
- Per-corner radius on a shape (sketch) and shape label padding are not built (wb5-1026 row 2).
- K24 Live view inside boxes: not built.
- K16: resizing a note or image card leaves the contents small in a large box (partly done).
- Layer order (four z-render sites and order commands): untouched, an Opus job with an elementFromPoint pair sweep.
- Real touch (isMobile pointer events) for grips and the slide after a tap-select, the real OS clipboard and a spreadsheet paste: not driven here.
- Headless Chromium paints no caret, so caret position after Enter was read from the selection range, not seen.
- Dark-mode phone sticky edit, frame move and duplicate with contents, pages and comments flows: not dogfooded in this pass.
