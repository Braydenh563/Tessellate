# whiteboard-1018: WHITEBOARD_PLAN open items (Sonnet agent, port 8798, data /tmp/mm-wb1018)

Audit, 2026-10-18, read from the code and tests (grep first, CLAUDE.md 1). "Built" means the control and its test exist; the owner's questions and B61, B58 are left alone.

## Step 0: what the plan's "Placed" sections and "The draw.io programme" still hold

| Item | State | Evidence |
| --- | --- | --- |
| Placed 2026-09-21 (258 right-drag pan) | open, owner decision | the plan asks the owner; skipped |
| Placed 2026-09-23 (small conventions, documents half) | open, not whiteboard | skipped |
| Placed 2026-09-25 (419 arrange menu and meatball) | open, owner needs to say window size | skipped |
| Placed 2026-09-27 (411) | placed elsewhere | skipped |
| Placed 2026-10-05 `contrast.js` never visits a board | open (Opus, M) | not in scope of S steps |
| Placed 2026-10-07: 740 (hint edit, rotated edge arrows, arrowheads), 746, 747 Reset style, edge arrows on resize | built, block still in the plan | `wbEditFrameTitle(.., "hint")`, `wbCloneSource` rotation, `reset-style` command, `tests/test_wb_rotate_links.py`, `test_wb_clone_grips_follow.py`; moved to HISTORY in step 1 |
| Placed 2026-10-11 INBOX 821 to 825 | built (code comments cite each) | `wbFrameFit`, page row rename, line popover, Layers head, Show more measure, guides; moved to HISTORY in step 1 |
| Placed 2026-10-11 INBOX 826 C1 to C4 | built (already in HISTORY) | |
| 826 C5 (the audit table, top five per surface) | open | this file, below |
| 829 board and map previews P1 to P3 | open, marked "the owner's call" in wbs-1011.md | skipped |
| Deepened rows 1 to 4 | built (HISTORY, Brief 77) | |
| Deepened row 6 (500 objects, paint visible first) | open, L, perf on an idle machine | skipped (load average) |
| Deepened row 7 (failed save says why, retries) | open | candidate |
| Deepened row 8 (every control has data-help-for and a palette row) | partial | candidate |
| Deepened row 9 (board AI act as a chat tool) | partial (`test_ai_whiteboard_tools.py`) | skipped |
| VC16 (p5 element) | open, L, owner decides the 239 KB cost | skipped |

### draw.io programme, sections 1 to 17 (open rows only; "Has it" in the plan's tables is stale in places: valign, elbow, ports, find and replace, edit data, current layer, tables, hand-drawn are built)

| Section | Open | Cost | This run |
| --- | --- | --- | --- |
| 1 Style | gradient, fill styles (hatch), custom dash pattern, corner rounding, flow animation, default style (Ctrl+Shift+D), board style presets, crop | S to M | steps 3 and 4 |
| 2 Text | font family, underline and strike, label background, spacing, text opacity, label position, text direction, line height, auto-size, clear formatting, font size up and down, remove from group, copy and paste size, turn 90, constrain proportions, reverse | S each | steps 2 and 5 |
| 3 Edit style | placeholders `%name%`, tooltip | S, M | step 7 |
| 4 Connectors | jump size, perimeter gap, reverse, clear waypoints, entity and isometric routes, rounded polylines, connector shapes (double, pipe) | S to M | step 6 |
| 5 Ports | custom port offsets, port add and delete, show or hide grips and ports | S, M | after |
| 6 Layers | layer order | S | step 8 |
| 7 Libraries | JS-drawn shape classes, drop a library item onto a connector, replace keeping connections | L | skipped |
| 8 Templates | insert a template into the current board, draw.io's templates | M | skipped |
| 9 Find | regex, whole word, find in props, tags | S | step 7 |
| 10 Outline and view | fit page width, enter group, grid size | S | after |
| 11 Keys | Ctrl+Shift+Z, Backspace, select all shapes and connectors, Ctrl+Delete, Home, F2, Ctrl+U | S each | with the commands |
| 12 Containers | table merge and stripes, child layouts | M | skipped |
| 13 Images | crop, math | M, L | skipped |
| 14 Export | JPG, WebP, copy as image, `.drawio` export, PNG with the board embedded | S, M | step 9 |
| 15 Insert | shape picker at the cursor, picker on a drag from a grip | M | skipped |
| 16 Layouts | flow, tree, organic, circle, parallel edge spacing | L | skipped |
| 17 No selection | grid size, paper size, options | S | after |
| Build first 6 | obstacle-avoiding elbow router (A*) | L | skipped (needs a 200-item timing on an idle machine) |
| Build first 10 | `.drawio` export, templates | M, L | `.drawio` export only if time |

## Steps, in order (each: tests first, one commit, measured at 1440 and 390)

1. Docs hygiene: the built Placed blocks to HISTORY.
2. Text tab: underline, strike, font family; Ctrl+U; clear formatting; font size up and down.
3. Style tab: corner rounding, custom dash pattern, flow animation.
4. Style tab: gradient and fill styles.
5. Commands: select all shapes, select all connectors, turn 90, remove from group, copy and paste size, auto-size, reverse.
6. Connectors: jump size, perimeter gap, clear waypoints.
7. Find: regex and whole word; placeholders and tooltip.
8. Layer order.
9. Export: JPG, WebP, copy as image.

## Done and next

(append two lines after each commit)
- done: Text tab (underline, strike, font, clear format, font steps), see git log; next: step 3 style tab (corner rounding, dash pattern, flow), whiteboard-format.js + whiteboard.js sketch paint
- done: Style tab Dashes, Corners, Flow; next: step 4 gradient and fill styles (whiteboard.js sketch paint, defs; export clones defs), then step 5 commands
- done: Style tab Gradient and Fill style; next: step 5 commands (select all shapes and connectors, turn 90, remove from group, copy and paste size, auto-size, reverse)
- done: step 5 commands (eight rows; wbFmtEntries keeps connectors); next: step 6 connectors (jump size, perimeter gap, clear waypoints)
- done: step 6 connectors (jump size, gaps, clear bends); next: step 7 find (regex, whole word, placeholders, tooltip)
