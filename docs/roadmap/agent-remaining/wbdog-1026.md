# wbdog-1026: whiteboard dogfood (INBOX 1358)

Scripts live in the session scratchpad (`wbdog/`), not the repo. Student story at 1440x900 and 390x844, light and dark; 23 driven scripts (d1 to d23), about 60 checks.

## Done (class, fix, test)
- **Selection by first match**: Format panel Bold and Italic wrapped the first occurrence of the words, not the selected ones; now by offsets, a second press unwraps (`wbWrapRange`, tests/test_wb_wrap_range.py).
- **Ghost selection**: an undone paste left ids in `wbMultiSelection`, so Export > Selection threw; `wbPruneSelection` runs first in every render (tests/test_wb_prune_selection.py).
- **Text hidden behind a scroll bar**: a text box or sticky grew only on blur; now grows as you type (`wbGrowBoxToWords`, tests/test_wb_grow_box.py).
- **Words overflowing a shape**: a label longer than the shape spilled out; the shape grows in proportion until it fits (`wbGrowShapeToLabel`, tests/test_wb_grow_shape.py).
- **Find and Replace skipped table cells**: "0 matches" for a word inside a table; cells are searched and replaced, one undo (tests/test_wb_find_cells.py).
- **No keyboard-only path** (WCAG 2.1.1): N, Enter did nothing and a selected sticky needed a double-click; `wbKeyboardEnter` places the held tool at the view centre and edits a lone text box (tests/test_wb_keyboard_enter.py, Keys sheet row, Guide topic board-keyboard-create).
- **Export drew boxes as words**: SVG, PNG and PDF had one `<rect>` (the background) for a board of a sticky, a text box and a table; text boxes now export paper, border and per-corner radii, a table its grid and words (`wbSvgBoxBackdrop`, `wbSvgTable`, tests/test_wb_export_boxes.py). Rasterised pixel check: sticky paper 253,230,138 light and dark; a plain box takes the theme fill. Pictures with per-corner radii still export square; a sticky's folded corner is not drawn.

## Layer order (wbz-1026)
- **Six sites, one order**: the SVG sort (z, id), the cards' z-index (z, then DOM append order), the export (frames, drawings, notes, objects, each in array order), the Layers tab and its drag restack (z, id across kinds), the locked-item hit test and the order commands each decided "on top" their own way. `wbStackOrder` / `wbStackCompare` (bands: frames, drawings, cards; then z; then notes before objects, then id) is now the one answer; the cards paint by stack rank (`wbStackRanks`), new items take `wbStackNewZ` (top of their band; a frame under the other frames), `wbFrameZ` is gone (tests/test_wb_stack_order.py).
- **Pair sweep** (session scratchpad `wbz-pairs.js`; 45 pairs of sticky, text box, shape, frame, picture, table, connector, note card, pen stroke; `elementFromPoint` at the overlap): painted vs the board's own order 92 to 0 (create 12 to 0, Bring to front 20 to 0, Send to back 21 to 0, reload 21 to 0, export 18 to 0); newer-on-top after create 19 to 11; undo 0 to 0.
- Left (41 of 45 x 3 expectation checks): a drawing never paints over a card, so Bring to front on a shape, line or pen stroke under a card, or Send to back on a card over one, changes nothing seen, and a drawing made after a card lands under it. The drawings are one SVG layer under the card layer; interleaving them needs per-item layers.

## Found, not fixed
- Drawings and cards cannot interleave (above: 11 create, 15 front, 15 back of 45 pairs). A frame's 1.5px edge, in the card layer, paints over a drawing inside it.
- `wbBoardToClient` read 16px left and 60px high of the item under it at 100% (the sweep maps through `#wb-zoom-group`'s screen matrix instead); it places the paste chip.
- Templates, Mermaid and draw.io inserts, the map and the library still write fixed z values (1, 2, 5) for the items they make; the stack orders them, but they can land under what was there.
- Per-corner radius on a shape (sketch) and shape label padding are not built (wb5-1026 row 2).
- K24 Live view inside boxes: not built.
- K16: resizing a note or image card leaves the contents small in a large box (partly done).
- Real touch (isMobile pointer events) for grips and the slide after a tap-select, the real OS clipboard and a spreadsheet paste: not driven here.
- Headless Chromium paints no caret, so caret position after Enter was read from the selection range, not seen.
- Dark-mode phone sticky edit, frame move and duplicate with contents, pages and comments flows: not dogfooded in this pass.
