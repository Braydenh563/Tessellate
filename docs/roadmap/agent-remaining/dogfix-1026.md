# dogfix-1026 (mapdog and docdog found-not-fixed, Sonnet)

Port 8797 (8796 was held by another agent). Not pushed.

## Done
- 1 map topic bar wrap: divider hidden under 600 and three columns under 600, in library-lazy.css (the boot CSS is at its cap). `scratchpad/ui-sweeps/mapstripwrap.js` at 390/375/360/320: no stranded divider, no lone control (root 3+2, child 3+3 or 3+2; was 348x102 with the reset alone). Other bars with dividers (`.wb-topbar`) already hide them under 600; the `.dock`s that stack at 390 (notes, graph, library, timeline) wrap by zone, with no divider.
- 2 deep-topic pan: not the reveal rule. The browser scrolled `#whiteboard-container` (overflow hidden) to centre the focused editor, 351px with the zoom transform unchanged. `wbFoldNativeScroll` folds any such scroll into the transform, the text editors focus with `preventScroll`, and `wbMapRevealTopic` now slides by the least move (24px inside the edge). `scratchpad/ui-sweeps/mapdeeppan.js` (Tab x5 under Cells, 1440x900): new topic ends 24px inside the right edge each step, parent always visible, root at x=96 after step 2 (was 16); `tests/test_wb_native_scroll_1026.py`.

## Found, not fixed
- 3 root width: `maprootwidth.js` (1440x900): a template root with a 26 character board name is 180x140, four lines, because the centre's ellipse takes `padding-inline: var(--space-7)` off both sides (text column about 100px); a plain-API root is 200 wide and wraps to 3. The width is persisted data (200 default, 180 in templates, the resize grip), so a "widen the root when its words wrap past three lines" rule has to write a width, or the ellipse padding has to shrink; not done, needs a decision.

- 4 Live scroll: profiled, not fixed; see docdog-1026 "Found, not fixed" (native layout and paint, not script).
- 5 More menu at 600: measured, not broken (4 rows, 486x191, none outside).
- 6 lone-span paste: done (`docHtmlIsRich`), 8 of 8 paste cases.

## Next
- Live DOM layout cost (`contain` on `.cm-line`, fewer wrapper spans) with `doclivescroll.js`; root width decision; comments, delete and restore, math driven for real use.
