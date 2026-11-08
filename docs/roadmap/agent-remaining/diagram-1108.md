# diagram-1108 (INBOX 1661 g, h, i), branch agent/diagram-1108

Done (one commit): the overlay (boxes, rings, handles, arrow ends, name field) is a zero-size origin inside the picture figure, so a scroll moves
them with the drawing; a redraw gives the pane its scroll back (diagram-view.js); a press on empty canvas or empty list and Escape clear the
selection (`S.clear`, diagram-canvas.js; the dialog's Escape clears before it closes); Canvas and Blocks are now Picture and List (ids kept), with a
hint line in both About popovers and a Guide line.

Measured (untracked sweeps in /tmp/d1108: verify.js, desel.js, scroll2.js; port 8895):
- Before: after a handle add on a scrolled pane, the redraw reset the pane to scrollTop 0 and the rings and field stayed 247 px off (the owner's "Step over Ship it"); at 390 the worst ring-to-drawing error over 20 adds was 315 px.
- After: 20 adds, 5 on each of the four sides, 1440 light and dark: 0 box intersections, ring error 0 px against the drawing's own node positions, ring and input offset unchanged by a pane and page scroll (0 px). 390: 13 adds, 0 intersections, 0 px.
- Empty canvas press, Escape and an empty list press: aria-selected rows 1 to 0, boxes on 1 to 0, handles 4 to 0 (after the 350 ms hover timer), one tab stop kept.

Not verified: the dialog's own Escape (diagram-embed.js) and the phone's list sheet were not driven; real touch; the other kinds (mind map, sequence, timeline) have no overlay and no clear-on-press; a screen reader.
Found, not fixed: the new box is not scrolled into view except by the name field taking focus; the node box and name field centres differ by 4 to 5.5 px (field is 32 px tall at a fixed offset); a Shift marquee ends in a click, ignored for 400 ms.
Left (owner's (j), the deeper redesign round): features, ways to do things, look; see INBOX 1661.
