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
- Phone strip (390x844): the topic bar is two rows, 348x102; the divider ends row 1 and the reset sits alone on row 2. Its rule documents the wrap as intended; polish is to drop the divider when wrapped (the controls total about 345px against 346px available).
- A new topic added past the right edge pans the view by 627px so the root ends 16px from the left edge (1440x900, Maths > Biology > Cells). It is the reveal-the-new-topic pan; it works, it just leaves the root almost off screen.
- A long board name makes the root box four lines at about 120px wide ("C career-map 1793027349720"); level-1 topics are 155px. A root name wrapping to four lines before it widens is worth a max-width look.
- Not driven: images and notes on topics, cross-links (links already covered by existing sweeps), export PNG (the board menu's `wbExportBoard` opens no `<dialog>`; its shape was not inspected), the 150-topic frame times on this run, the middle-button pan (needs the owner, per the inventory).

## Next
- Phase 3 inventory rows not reached: `mindmap-1018.md:38` (a filled Plain topic keeps its tint, a documented specificity tie), #712 (Add a top-level topic: Ctrl+Z leaves the lists differing), #715 (tool section labels 49 to 56px past their box), #1359 (name the layout on the map).
