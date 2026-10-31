# Deep audit 2026-10-31: board (whiteboard, mind map, present, library sidebar, export, board routes)

Fable suite, surface 4 of 12. Server on 8852. Boards: "Harbor launch board"
(76, 9 objects, 9 sketches), the "Portugal trip" map (77, 18 topics), and a
seeded "Audit big board" (211: 302 text objects, 60 sketches, made through
the API in 9.1 s). Drives hb1 to hb4 (Playwright, 1440 and 390, dark; network
requests to `/whiteboard` counted per step) and an API probe. Observed unless
marked code.

## Rows

| Row | Sev | Kind | Finding | Evidence | Where | Verified | Fix | Size |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BD1 | high | bug | **One far object breaks the whole board, and the API lets it in.** `x` and `y` are unbounded floats (`width` and `height` are 20 to 4,000): `y: 1e308` was stored (201). With two such objects on the 362-item board, 100% zoom put every item at y = −33,554,310, zoom to fit showed nothing (all 302 objects culled at every zoom), and PNG export failed with "Couldn't rasterize the board." Deleting the two restored the board. `"x": "NaN"` answers 500 "Something went wrong inside Tessellate" (ref ca738867…). | API probe; hb2 drag-visible "none visible", hb3 find `y: -33554310, culled: 302`; hb3b after the delete; export-png toast | `routes_whiteboard.py:776` `WhiteboardObjectBase` (`x: float = 0.0`, `y`, `z` unbounded; `allow_inf_nan` default), same for sketches `:331` | run | `Field(ge=-1e6, le=1e6)` on x, y and z, `allow_inf_nan=False` on the models; clamp on the client before save; a board-open check that drops items outside the limit with a toast. | S |
| BD2 | high | perf | **Moving a selection writes one request per item.** Ctrl+A on 362 items then two ArrowRight presses sent 167 `PUT /whiteboard/objects/N` (44 within 1.5 s, 123 more trailing into the next step) with long tasks of 189, 274 and 264 ms; undoing one map child sent `DELETE` plus 17 `PUT /objects/N`. `/boards/N/nodes/move-many` exists and is used for map tidy only. 1028 B38 confirmed. | hb1 select-all-nudge, delete-undo `reqs`, map-77 `reqs2` | `whiteboard.js:5538` `wbNudgeSelection` → `:22875` `wbSaveObject`; `whiteboard-map.js:8422` | run | A `/boards/N/objects/move-many` body for every multi-item move, nudge and undo; one request per gesture. | M |
| BD3 | med | perf | The big board costs: 1,223 ms to first items with a 396 ms task; Ctrl+A renders 2,789 handle elements; a marquee over the board blocks 333 ms; opening the export dialog blocks 241, 361 and 229 ms (it renders a preview); the map (18 topics, 662 nodes) opens with 206 and 248 ms tasks. Culling works (157 of 302 culled at 100%, 3,947 nodes). | hb1 open-big, select-all-nudge, export-menu; hb2 marquee; hb1 map-77 | `renderWhiteboard` (890 lines), `renderWbObjects` (870), `wbRenderMultiSelectionHandles` (334) | run | One selection outline for a multi-select instead of per-item handles; preview the export on idle; 1028 B3/B4 dirty-set render. | M |
| BD4 | med | a11y | `#wb-rail-ink` is an `input[type=color]` carrying `aria-haspopup="dialog"` and `aria-expanded` (axe aria-allowed-attr, critical); `#wb-zoom-level`'s label "Zoom level, press for 100%" hides its visible text ("143%") (label-content-name-mismatch, serious). Both at 1440 and 390. | hb1 toolbar axe; hb2 phone-open-76 axe | `index.html:7612`, `:7661` | run | Move the popup attributes to the button that opens the well; label the zoom button "Zoom 143%, press for 100%" from its text. | S |
| BD5 | med | ux | A locked item shows nothing: after "Lock" the object gains `wb-locked` with no glyph element, `aria-label` or `title`; only hover tells. 1028 B20 open. | hb4 lock `g: {cls: "… wb-locked", glyph: 0, title: ""}` | `whiteboard.js` lock rendering | run (glyph element; CSS badge not measured) | A small lock glyph in the item's corner, in the accessible name too. | S |
| BD6 | med | a11y | On a phone the selection handles are 10 x 10 (90 handle elements after one tap on board 76) and the main toolbar has no visible buttons at 390 (a floating tools panel takes over; its targets not measured). 1028 B27. | hb2 phone-tap-object `handleBox: 10x10`, phone-open-76 `tools: 0` | handle renderer `:20530` area | run | 24 px hit areas on coarse pointers (`@media (pointer: coarse)`), one outline plus corner grips. | S |
| BD7 | med | arch | Sizes: `whiteboard.js` 25,569 lines, 553 functions, `initWhiteboard` 4,090 lines; `whiteboard-map.js` 10,929 lines; 319 `addEventListener` against 7 `removeEventListener`; 15 `pointermove` listeners; 5 `console.` calls. 1028 B1, B2, B5, B6, B22 open. | counts | files | code | Split by feature (tools, selection, render, export, present, map) with one listener registry torn down on board switch. | L |
| BD8 | low | a11y | Boards landing: the five "Board: …" open buttons are 269 x 22. | hb1 landing `small` | landing card renderer | run | 24 px minimum. | S |
| BD9 | low | a11y | Tab moves the selection inside the canvas with a live announcer ("Text box: Card 3 …, 4 of 362, selected") but no `aria-activedescendant`, so assistive tech has a region and no focused object. | hb1 keyboard-tab | `#whiteboard-container` role application | run | Set `aria-activedescendant` to the selected item's id. | S |
| BD10 | low | ux | The context menu is 17 flat items, 629 px tall, no submenus (Copy, Cut, Comment, Link, Export selection, Copy as image, Copy as SVG, Save to the library, Save this style, Save as a preset, Save these colours, Lock, four z-order items, Delete). 1028 B26. | hb4 context | `wbBuildContextMenu` (458 lines) | run | Group "Save…" and z-order into submenus. | S |
| BD11 | low | ux | Dismissing the empty-board hint leaves only "Board · Audit empty (0 items)"; the way back is the Help sheet. 1028 B34. | hb1 empty-board | `wb-empty-hint` | run | A faint "Press ? for the keys" line on an empty board. | S |
| BD12 | low | ux | Each PNG export also adds a copy to the image library ("Board exported as PNG, and added to your image library."), unasked; two exports, two copies. | hb3, hb4 png-76 toasts | export path | run (copies in the library not counted) | Make the library copy a checkbox in the export dialog. | S |
| BD13 | low | a11y | Closing the Keys and controls sheet puts focus on `#tab-library`, not the button that opened it (same class as SH5). | hb1 help-overlay `after` | `wbOpenHelpSheet` | run | Restore to the opener. | S |
| BD14 | low | security | Sketch `data` is an opaque string of up to 400,000 characters; the path, colour and width inside are not validated server-side (a client-side JSON parse guards the render). | `routes_whiteboard.py:331`, `:57` | code | Parse and bound `d`, `width`, `color` on write. | S |

## 1028 board rows re-verified

| Row | Now | Evidence |
| --- | --- | --- |
| B1, B2, B5, B6, B22 sizes and listeners | open, BD7 | counts |
| B3, B4 render cost | partly, BD3 | culling exists; multi-select and marquee still block |
| B13 shortcut sheet | fixed | `#wb-help-overlay`: dialog, 74 rows, search box focused |
| B20 lock badge | open, BD5 | |
| B27 handle size | open, BD6 | 10 x 10 on touch |
| B34 empty hint | open, BD11 | |
| B38 per-object PUT | confirmed, BD2 | |
| B10 PDF | present as a format | export dialog lists PDF (not run) |
| B8, B9, B16, B21, B23 to B25, B28 to B33, B35 to B37, B39, B40 | code rows, not re-run | |

## Coverage

| Area | Driven | Notes |
| --- | --- | --- |
| Open board (small, 362 items), map; landing | run | `role=application`, announcer, culling |
| Toolbar, zoom (fit, wheel, 100%), pan with Space | run | wheel zoom and pan logged no long tasks on the big board |
| Drag one object | run | 160,80 moved, one PUT, persisted (1980, 1160) |
| Select all, nudge, marquee, delete, undo | run | delete: one DELETE; undo: one POST (new id) |
| Context menu, lock | run | |
| Text edit by double click | run | one PUT on Escape; no request per keystroke |
| Export PNG and SVG (dialog: PNG, JPG, WebP, Copy image, Image library, SVG, Outline, Mermaid, draw.io, PDF; scope; scale) | run | PNG of board 76 281 KB in 325 to 719 ms; SVG of the big board 633 KB in 176 ms |
| Present | run | no frames: returns with a guidance toast (`whiteboard.js:25145`) |
| Help sheet, sidebar (Library, Notes, Layers, Pages; 172 items) | run | |
| Map: add child with Tab, type, undo | run | child added and removed; 17 PUTs on undo (BD2) |
| Phone: board and map open, tap select | run | map root visible at 72%; board at 19% |
| API: object and sketch schemas, caps (20,000-char text, 400,000-char sketch), NaN, huge coordinates, thumbnail, import, propose, export | run | import and propose validate their bodies; `/boards/N/export` returns Markdown |
| Frames, connectors and arrow binding, ink and eraser on touch, images (paste, drop), templates, stickers, layers, pages, comments, draw.io and Mermaid export, PDF, duplicate board, generate from notes | not driven | |

## Already good

- A single drag, delete, undo and text edit each cost one request; typing sends nothing until Escape.
- Culling keeps a 362-item board at 3,947 nodes; wheel zoom and pan on it logged no long tasks.
- The Keys and controls sheet is searchable and focused on open; the empty-board hint names the tools, the keys and "Don't show on new boards".
- Width, height, rotation, group ids, text length and sketch length are bounded; unknown kinds are refused with the list of valid ones; image URLs must be same-origin.
- Present without frames explains what a frame is instead of doing nothing.

## Not verified

- Frames and the present flow with frames, connectors and arrow re-routing, eraser on touch (B21), image paste size limits (B28), PDF export, the phone tools panel's targets, whether CSS draws a lock badge from `wb-locked`.
