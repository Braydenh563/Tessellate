# dgmfix-1108 (blind test of the diagram builder, head 56593261)

Branch agent/dgmfix-1108. Server was on :8776 (8796 was taken by another worktree's server), data /tmp/dgmfix-data.

## Log

- 72c00da8 items 1 to 4.
  - 1: the shelf took the Add library's glyph nodes (`tileOf` appended `t.glyph` itself), so the phone sheet's slot held the name text for Participant, Message, Reply, Note, Loop, Alt (6 of 13 rows). `tileOf` clones; the sheet picks `:scope > :not(.dgm-tile-name)`. After: 13 of 13 rows hold an icon in the 24 px slot at 390x844 touch. The shelf's caret menu rows wear the glyphs (8 of 8 rows, 20 px slot, 1440x900).
  - 2: Kind change with content asks in `confirmDialog` ("Switch to sequence diagram? The 3 boxes will be cleared." Switch / Keep flowchart); cards stay 3 until Switch, then 0. A blank diagram switches at once.
  - 3: a tile dropped on empty picture joins the nearest box within 120 px (`math.nearest`), else the selected box; drop at 70/60 now gives "Start, box, 2 connectors"; caption "Add, joined from Start" at y 399 to 425 inside the picture (180 to 733). Tile tooltip and idle hint say "onto the picture".
  - 4: `diagram-embed.js` keeps `diagram-drafts` (5 max, 14 days, 2 MB; key = caller's `draft` plus a hash of the opening source) on change and `pagehide`; the next open asks in the confirm ("Put back your unsaved changes?" Put them back / Start fresh), not a toast (a toast over this dialog is dimmed to 0.12 and unpressable, `toastYield`). Done and a confirmed Discard forget it. Measured: reload with 4 cards, reopen shows 3, Put them back gives 4, Discard leaves no stored draft.
- Next commit: items 5 and 6 (handle clamp in diagram-edges.js `showHandle`; `.dgm-sideways` out of the flow, 0 px shift of shelf, body and picture, light and dark, 1440x900).

## Left

- Item 5 on a phone: the clamp keeps every handle inside `fig.scrollWidth/scrollHeight`; the tester's layout (box 15 px under the pane top, 44 px handles) was not reproduced (handles measured 24 px, clip 1 px on the left before and 0 after). The handles still overlap a box's edge by up to 12 px; a lean-out for coarse pointers was not added.
- Item 6 on a phone: the offer did not appear at 390 (the chart must be wide-pane and tall), so only 1440x900 was measured.
- Guide topic `diagram-blocks` is at 1893 of 1900 characters, so the drop-joins and kind-asks sentences are in the dialog's help text only; `test_manual_parity` pins the old Guide sentence.
- The kind menu's `decorate` (diagram-kindbar.js) looks for `.pointer-menu-host .action-menu`; the menu can be moved out of its host, as the shelf menu was. Not checked.
- Not measured: the far bottom-right corner of the picture (95 percent, 95 percent) took no drop (the zoom bar is there).
