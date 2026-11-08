# doclist-1108 remaining

Branch `agent/doclist-1108`. Port 8798, data `/tmp/doclist-data`.

## Log
- L1 done (next commit hash in git log): Enter continues `a.`, `i.`, dash items.
- L2 was already built (prose pairs exist); verified in the editor, docs only.
- L4 done: Mod-Alt-g goto line in prose + palette row.
- L3 was already built (grammar folds list items); verified, docs only.
- L5 done: #tag completion in markdown.

- Settings lag (item 1) done: `settingsIndexHeads.shown` reads the tree, no `getClientRects`. 4x CPU, 3 runs, Help: first heads 70/82/103 ms to 0.7/0.2/0.1; first build 80/94/111 to 2.3/0.5/2.1. Other sections' first heads: general 13.6/4.8/9.2 to 0.1/0.1/0.9; personas 8.5/6.2/34 to 0.1/0/0.1.

## Left
- Nothing in the brief. Not verified: the layout cost now lands on the next frame's own layout (not measured as frame time); a head hidden only by a media query or an unusual class would now be listed (none found on 21 sections at 1440 and 390).
- Found, not fixed: `#tag` typed in a document has no meaning to the app yet (no chip, no search by it); the completion only offers the names. L3's fold carets show only with Line numbers on.
