# dgmlive2-1108: remaining

Branch `agent/dgmlive2-1108` (not pushed). Port 8899. Sweeps are in the agent scratch dir, untracked; tests are `tests/test_diagram_dgmlive2_1108.py` (source checks).

Done (one commit each, see `git log`): Library focus, undo redraw and archived listing, plus the embed More focus (one commit); the double click on an embed; the purpose line's reserved height (first hover moved the list 17px, so the first click on a block's ⋯ opened nothing: tree y 273.8 to 257 before, steady after); the app's Ctrl+Z waits behind a dialog (it undid a rename behind "Switch to mind map?").

Blind pass (flowchart from empty, 1440 wide): six boxes by the shelf tile, each opens in-place rename (typing names them, Enter ends); a Decision's first join offers a "yes" field, the second is labelled "no" by itself; undo 6 to 5 to 4 joins and redo back to 6; shape menu; kind menu confirms "Switch to mind map?"; Save as SVG downloads. No other break found.

Left:
- Library card menu has no Duplicate row for a document or diagram (the brief expected one); a new feature, `libraryActions` in `frontend/js/library.js` near line 1061.
- Ctrl+Z after a keyboard delete in the Library leaves focus on BODY (the toast Undo and the menu rows are fine); `documents-undone` redraws, but focus was on the toast.
- The toast "Undone: last change on this document" says nothing about what; `docUndo` in `frontend/js/documents.js` ~15663, text pinned by `tests/test_link_types.py:137`.
- New boxes are all named "Step" until typed over; the typing-over works, so left as a design choice.
- Not verified: the purpose line at 390 wide (three lines may not be enough there), touch, dark theme, a screen reader.
