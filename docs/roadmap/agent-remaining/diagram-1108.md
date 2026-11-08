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

## Round j1 (quick ways to build; sweeps in /tmp/d1108: q1.js q3.js q4.js, port 8895)

Picked from the research (strong tools: draw.io, Whimsical, Miro, Lucidchart, Mermaid Live) for a first-time user, after checking what already existed
(multi-select, marquee, Colour, undo and redo buttons, zoom, handle quick-add, Tab chain, PNG, SVG and Mermaid export were there):
1. Double press on empty picture adds a box and names it (blocks 3 to 4, name field open).
2. Ctrl+D copies the picked blocks (3 to 4 blocks and boxes; one Ctrl+Z restores 3).
3. Ctrl+A from the picture picks every block (selected rows 1 to 3).
4. Delete on the picture removes the picked blocks (3 to 0; Ctrl+Z gives 3 back).
5. Shift+Enter adds a joined box after the picked one and names it; Alt+Enter adds a sister joined to the same parent (list: Plan | Build | Review under Build).
6. Find, Ctrl+F or / on the picture: a dock with a field and a count; matching boxes get a dashed accent ring (found 1 for "bu"), Enter walks them and picks the box (1 of 1), Escape closes and returns focus. Bar 350 x 38 at 1440, 286 x 54 at 390, inside the stage, no overflow.
7. Reverse direction in the connector menu (Plan to Build became Build to Plan; A box top 372 and B 456 swapped to 498 and 414). Refuses a duplicate.
8. The Keyboard shortcuts sheet and the Guide's diagram-reading topic (1,847 characters, cap 1,900) list the new keys.
Found and fixed on the way: delete every block, then Undo, made a second overlay (6 boxes for 3 blocks, 2 layers), so rings and handles painted twice: the overlay is now made once per figure (`fig.dataset.overlay`); 3 boxes and 1 layer after the same steps. Tests: tests/test_diagram_1108b.py.
Not built (cut for time, from the ten): hover quick-add preview ghost, alignment guides (auto-layout, so no manual positions), a visible name on the Undo button (the history mixes source edits, so the name could go stale).
Not verified: the dialog's Escape against the find field (the dialog listens at document capture), real touch, screen reader; kinds other than flowchart have none of this. The click on a connector chip selects it; its menu opens on Enter.
Left of the open DD items, untouched: DD-5 completion list, DD-10 drawn sample, DD-12 Versions, DD-13 spacing, DD-15.
