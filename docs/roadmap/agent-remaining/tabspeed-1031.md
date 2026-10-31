# tabspeed-1031 (INBOX 1492 frontend half: tab switch, openDocument, CodeMirror measure loop)

Setup: worktree wt-tabspeed, port 8848, data /tmp/claude-0/tabspeed-data (copy of a 500-note notebook), 4x CPU throttle. Scripts live in /tmp/claude-0/tabspeed-scr (not in the repo): `tabbench.js` (click event duration), `cpu.js` (style, layout and paint totals per click, one variant per process), `trace3.js` (timeline).

Before (4x, 500 notes, 1440 wide, median click): notes 544 to 720, dashboard 392 to 424, library 256, graph 384. The host is noisy (load 6 to 7): wall-clock A/B inside one page flipped sign between runs; only per-process style and layout totals (`cpu.js`) repeated.

Causes found
- The click is mostly rendering, not script: LoAF shows 72ms of script (56 forced) and about 284ms of style and layout after it.
- Notes click makes three style passes: 601, 1075 and 1794 elements (66 + 71 + 116 to 230ms), each after a layout, 3,470 elements restyled for a tab with about 1,100 rendered ones. Layout is about 95ms in three passes.
- Cause of the extra passes is not the shells' `content-visibility: auto` (shell content-visibility off: 346 to 308ms of style, same three passes; shells `display:none`: 306, same three passes). Not container queries either (`container-type: normal` on the tab: no change).
- Hiding tab roots with `content-visibility: hidden` (kept style) instead of `display:none`: style 441/289 to 209/180ms, layout 93 to 51ms, one pass of 1,852 elements. Not adopted yet: it changes `offsetParent`, focus and geometry reads for everything in a hidden tab.
- Style matching is about 48ms of a 1x reveal (299k selector attempts, 1,649 selectors): largest are `:where(.modal-overlay, .lock-overlay:not(#lock-overlay), #palette-overlay):not(.hidden)` (4.3ms), `#entry-list li:is(:focus-visible, :has(:focus-visible))` (3.8ms) and the `:has(textarea, ...)` content-visibility rule (2.6ms), the last two run on all 515 `li`.

Failed twice (do not repeat): wall-clock A/B in one page with alternating CSS variants (noise larger than any effect); a cached `notesScroller` (owner3 note).

Next
- cheap selector fixes: give the shell `li` a way out of the `:has()` rules (`li:not(.row-shell)` first), the modal-overlay `:where` list.
- decide on `content-visibility: hidden` for hidden tab roots, with a test of what reads geometry in a hidden tab.
- openDocument forced layout with a 300-line doc; CodeMirror measure loop (`docStickyScroll.write`).
