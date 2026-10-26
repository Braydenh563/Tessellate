# tabcost-1017 (Sonnet, worktree-agent-a7b541f59a174734f)

Brief: cut the Timeline tab's remaining entry cost (about 1.16 s of UpdateLayoutTree at 4x, a 37-96 ms recalc of 480-780 elements per `appendTimelineRows` chunk), then Library `renderLibrary`/`libraryCard` and Notes `renderNotesRail`, with no visual change.

- done: the per-chunk restyle was four `:has()` anchors with a universal child (the collapsed sidebars' keyboard peek in 07 and 08, the opened row's `::first-line`, Atlas's blink), each restyling the whole card on every insert. Rewritten as variables and sibling selectors; `tests/test_tab_entry_cost.py` holds it.
- next: re-measure the Timeline entry at 4x and 1x; chunking options (fragment, first chunk, `markScrollEdge`) only if the numbers still justify them; then Library and Notes.
