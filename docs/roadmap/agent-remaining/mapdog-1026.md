# mapdog-1026 (mind map dogfood, Sonnet)

Brief: owner INBOX 1358 (fix the class, not the case) plus K15. Port 8795; probe scripts live in the session scratchpad (`mapdog/js`), outside the repo.

## Done (3 commits, not pushed)
- K15 (30b6303): 27 of 27 templates store layout, root shape, per-level topic shapes and build what the picture shows; new shapes chevron and underline (API, strip select, pickers, CSS, thumbnails, Guide topic); a new map from a template is tidied once as it opens. Measured on Career plan, light and dark, 1440x900: root box over four chevron topics each with two underline leaves, text contrast 0 of 12 nodes under 4.5 in both themes (5 templates sampled: career-map, swot, causes, study, trip).
- Class "a picker row wider than its menu" (bc6b153): the Shape popup had nine previews in a never-wrapping run (306px in a 220px cell, Cloud and Plain cut off); more than seven choices now wrap as a grid. `tests/test_map_shapes_agree.py` holds the API, select, pickers, glyphs and CSS to one shape list.
- Class "opens at an unreadable zoom" (966dff4): `createNewBoard` fitted every board after opening it, undoing `wbFrameMapOnOpen`'s 1:1 fallback. Career plan at 390x844 opened at 16.7% (words 2px high); now 100% on the root. Pinned by a test in `test_map_templates_k15.py`.

## Verified clean (no change needed)
- Words stay inside every drawn shape (11 shapes x long label, 1440x900): left and right text margins 3 to 22px, the chevron's tip padding leaves 9 to 11px past the text at fit zoom.
- Persistence: shape, fill, collapsed state and the board URL survive a reload (5 topics probed).
- Keyboard-only: Enter on a map topic is a line break by the owner's 2026-10-10 decision (so `fixb-1025.md:5` is settled: leave it); Tab adds a child, Esc ends the edit, arrows walk, Delete removes, Ctrl+Z restores, Ctrl+Shift+Z redoes.
- Imports from the UI already tidy at open (`wbMapTidyFresh` at every import, document, notes and template call site); only a map POSTed straight to the API opens as a ladder.
- Popups at 390x844: Text, Shape, Branch line, Edit, View menus all inside the window (8 to 344px of 390); they scroll rather than clip.
- No console errors in any run (apart from the probe's own invalid `fill: "tint"`, a 422 by design).

## Found, not fixed
- Radial layout is large: 31 topics (6 branches of 4) lay out 1927x1771 board units, fit zoom 31% (words 4.4px); 57 topics 3653x3497, fit 16%. No overlaps (0 pairs). The size is the leaf label width (about 170px) on the outer ring, so the cure is narrower leaf boxes in radial, a design change; at fit below 45% a map now opens at 1:1 on the root instead.
- [x] Phone strip (390x844): done in dogfix-1026 (98931d6): divider hidden and three columns under 600; 390 root 3+2, child 3+3 (was 348x102 with the reset alone); 360 and 320 3+2. `mapstripwrap.js`.
- [x] Deep-topic pan: done in dogfix-1026 (98931d6). Not the reveal rule: the browser scrolled the overflow-hidden canvas to centre the new editor (351px, zoom transform unchanged). Folded into the transform, editors focus with preventScroll, reveal is the least move. Tab x5 under Cells: new topic 24px inside the edge every step, parent always visible, root at 96px after step 2 (was 16); the root still leaves the screen from step 3 on, because parent and child stay in view (deeper than three levels needs zoom-out, not a pan). `mapdeeppan.js`.
- Root width, measured not fixed (dogfix-1026): a career-map template root named "C career-map 1793027349720" is 180x140 (four lines at 1440x900, fit zoom 0.87, so 157px on screen; level-1 topics 180); an API-made root is 200 wide and three lines. The text column is about 100px because the centre's ellipse takes `padding-inline: var(--space-7)` off both sides; width is persisted data (200, 180 in templates, the resize grip), so widening needs a stored width or a smaller ellipse inset. Needs a decision. `maprootwidth.js`.
- Not driven: images and notes on topics, cross-links (links already covered by existing sweeps), export PNG (the board menu's `wbExportBoard` opens no `<dialog>`; its shape was not inspected), the 150-topic frame times on this run, the middle-button pan (needs the owner, per the inventory).

## Next
- Phase 3 inventory rows not reached: `mindmap-1018.md:38` (a filled Plain topic keeps its tint, a documented specificity tie), #712 (Add a top-level topic: Ctrl+Z leaves the lists differing), #715 (tool section labels 49 to 56px past their box), #1359 (name the layout on the map).
