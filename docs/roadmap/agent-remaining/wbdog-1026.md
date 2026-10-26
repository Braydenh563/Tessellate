# wbdog-1026: whiteboard dogfood (INBOX 1358)

Scripts live in the session scratchpad (`wbdog/`), not the repo. Student story at 1440x900 and 390x844, light and dark; 23 driven scripts (d1 to d23), about 60 checks.

## Done (class, fix, test)
- **Selection by first match**: Format panel Bold and Italic wrapped the first occurrence of the words, not the selected ones; now by offsets, a second press unwraps (`wbWrapRange`, tests/test_wb_wrap_range.py).
- **Ghost selection**: an undone paste left ids in `wbMultiSelection`, so Export > Selection threw; `wbPruneSelection` runs first in every render (tests/test_wb_prune_selection.py).
- **Text hidden behind a scroll bar**: a text box or sticky grew only on blur; now grows as you type (`wbGrowBoxToWords`, tests/test_wb_grow_box.py).
- **Words overflowing a shape**: a label longer than the shape spilled out; the shape grows in proportion until it fits (`wbGrowShapeToLabel`, tests/test_wb_grow_shape.py).
- **Find and Replace skipped table cells**: "0 matches" for a word inside a table; cells are searched and replaced, one undo (tests/test_wb_find_cells.py).
- **No keyboard-only path** (WCAG 2.1.1): N, Enter did nothing and a selected sticky needed a double-click; `wbKeyboardEnter` places the held tool at the view centre and edits a lone text box (tests/test_wb_keyboard_enter.py, Keys sheet row, Guide topic board-keyboard-create).
- **Export drew boxes as words**: SVG, PNG and PDF had one `<rect>` (the background) for a board of a sticky, a text box and a table; text boxes now export paper, border and per-corner radii, a table its grid and words (`wbSvgBoxBackdrop`, `wbSvgTable`, tests/test_wb_export_boxes.py). Rasterised pixel check: sticky paper 253,230,138 light and dark; a plain box takes the theme fill.

## Layer order (wbz-1026)
- **Six sites, one order**: the SVG sort (z, id), the cards' z-index (z, then DOM append order), the export (frames, drawings, notes, objects, each in array order), the Layers tab and its drag restack (z, id across kinds), the locked-item hit test and the order commands each decided "on top" their own way. `wbStackOrder` / `wbStackCompare` (bands: frames, drawings, cards; then z; then notes before objects, then id) is now the one answer; the cards paint by stack rank (`wbStackRanks`), new items take `wbStackNewZ` (top of their band; a frame under the other frames), `wbFrameZ` is gone (tests/test_wb_stack_order.py).
- **Pair sweep** (session scratchpad `wbz-pairs.js`; 45 pairs of sticky, text box, shape, frame, picture, table, connector, note card, pen stroke; `elementFromPoint` at the overlap): painted vs the board's own order 92 to 0 (create 12 to 0, Bring to front 20 to 0, Send to back 21 to 0, reload 21 to 0, export 18 to 0); newer-on-top after create 19 to 11; undo 0 to 0.
- Left (41 of 45 x 3 expectation checks): a drawing never paints over a card, so Bring to front on a shape, line or pen stroke under a card, or Send to back on a card over one, changes nothing seen, and a drawing made after a card lands under it. The drawings are one SVG layer under the card layer; interleaving them needs per-item layers.
- done: c09eaed. next: move the fixed z writes in templates, Mermaid, draw.io, map and library inserts onto `wbStackNewZ` (whiteboard-interchange.js 790-1071, whiteboard-library.js 754, whiteboard-map.js 4662); decide whether drawings may interleave with cards (an owner decision, INBOX entry).

## Done (wb5)
- **`wbBoardToClient` 16px left, 60px high**: the cause was a stale origin cache (a rect read while the canvas was hidden, dropped only by pointer events), so `wbClientToBoard` was off the other way too. Measured at zoom 1, 0.5, 2 and two pans, canvas hidden and shown: 20 of 20 coordinates off before, 0 after; the canvas now clears the cache on resize, the chip reads fresh (tests/test_wb_board_to_client.py).
- **Inserts on top** (wb5): Mermaid (flow and sequence), draw.io, Join, Place joined and the dragged link take `wbStackNewZ("sketch")`; the library's `/place` stacks its rows server-side (`_stack_on_top`: each band's next z, the stencil's order kept, frames under frames). Insert sweep over existing higher-z items (session scratchpad `ins.js`): same-band new-under-old pairs 16 of 16 before, 0 of 16 after (tests/test_board_library.py, tests/test_wb_stack_order.py). Map topics and links keep their own z (the map lays out; no overlap).
- **Export: picture corners and the sticky fold** (wb5): a picture with `radii` is clipped to them (`clipPath`), a sticky draws its cut corner and the fold from the computed `::after` gradient (`wbSvgStickyFold`). Rasterised pixel check (session scratchpad `exp.js`, 200x140 sticky, picture radii 60): fold tip 253,230,138 (paper) before, 255,255,255 (board) after; fold body 253,230,138 before, 197,179,108 after; picture corner 255,0,0 before, 255,255,255 after; a sticky with the fold off unchanged (tests/test_wb_export_boxes.py).
- **Table column widths** (wb5): `data.col_widths` (relative weights, mean 1; server refuses a count other than the columns), item-menu rows Widen, Narrow and Equal at the pressed cell, the grid tracks, the export and Add or Delete a column read them (tests/test_wb_table.py). Session scratchpad `tbl.js`: 13 of 13 checks; widened column 137.7px vs 110.1px, total 358px, Undo back to 119.3px each, export within 1px of painted, Add column keeps the others' pixels. Drag-the-border resizing is not built (menu rows only).

## Found, not fixed
- Drawings and cards cannot interleave (above: 11 create, 15 front, 15 back of 45 pairs). A frame's 1.5px edge, in the card layer, paints over a drawing inside it.
- Per-corner radius on a shape (sketch) and shape label padding are not built (wb5-1026 row 2).
- K24 Live view inside boxes: not built.
- K16: resizing a note or image card leaves the contents small in a large box (partly done).
- Real touch (isMobile pointer events) for grips and the slide after a tap-select, the real OS clipboard and a spreadsheet paste: not driven here.
- Headless Chromium paints no caret, so caret position after Enter was read from the selection range, not seen.
- Dark-mode phone sticky edit, frame move and duplicate with contents, pages and comments flows: not dogfooded in this pass.
