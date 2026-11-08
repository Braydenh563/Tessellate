# diagklm-1108: INBOX 1661 (k) (l) (m) and the scroll-into-view note, design spec

Branch `agent/diagklm-1108` from `claude/next-queue-1102` (7cba04a8). The spec is the brief for the build steps below; each step is one commit.

## Measured now (port 8921, New diagram dialog, sweeps kept untracked in the session scratch `dk/m.js`, `dk/seq.js`, `dk/gap.js`)

- 1440x900, both themes, same geometry: head 67+48, Title row 125+39, kind row `.dgm-kinds` 173+40 (four 70x32 buttons, 301 px wide, alone on its row), dock 231+46, sideways line 287+32, body 328+405, foot 755+40. Chrome from the head's top to the picture's top: **261 px**; picture **905x405** of a 1216x768 dialog.
- 390x844, both themes: kind row 189+52, dock 259+62, body 330; chrome **329 px**; flowchart picture 356x366. **Sequence picture 356x96**: its blocks list (325 px) stacks under it instead of being the `.dgm-listbtn` sheet (a bug; fixed in S3).
- Sequence, login template (User, App, Server, alt with else, a note), 1440: a press on the picture selects nothing (`aria-selected` none), a double press opens nothing; `diagram-overlay.js:52` returns for every `S.k` pane, so no rings, no handles, no rename field. The Add tiles exist only inside the Add sheet (`diagram-touch.js` wires it for every `S.k`). The flowchart toolbar has no tiles since D2 (Add split menu), so a drag from a library onto the picture has no source in either kind, though `diagram-canvas.js` `over` (lines 12 to 30) still takes a tile drop.
- Mermaid's sequence SVG tags every part: `data-et="participant" data-id="<id>"` (a `<g>`, its `rect.actor-top` next), `data-et="life-line" data-id="<id>"` (`line` x1, y1, y2), `data-et="message" data-id="iN" data-from data-to` (`line` x1, x2, y1), `data-et="note" data-id="iN"` (`<g>`, a `rect.note` next), `data-et="control-structure" data-id="iN"` (`<g>` of `line.loopLine`). `iN` counts Mermaid's statements: in the template i0, i1 messages, i2 alt, i3, i4 messages, i5 else, i6 message, i7 note, i8 the control structure.

## Research, the parts taken

- **draw.io**: shapes panel on the left, Ctrl+Shift+K folds it, Format panel on the right, Ctrl+Shift+P; drag a shape and a blue outline marks the drop; hover arrows clone and connect; double press, F2 or Enter edits a label in place. Taken: drop marker, in-place edit, a key per panel.
- **Excalidraw**: tools are a strip on the canvas with number keys; the library is a side panel that can dock or close; items drag onto the canvas. Taken: the library lives on the picture (a shelf), not in a side panel.
- **Scratch**: category rail and a palette flyout; a dragged block shows a grey shadow where it will snap. Taken: the insertion shadow (a line in the gap) and group-ordered tiles.
- **Mermaid Live / Mermaid Chart**: the kinds are named samples in a panel; panes fold and split; the visual sequence editor selects a participant or message in place and offers a "+" between messages. Taken: kind samples as pictures, "+" in the gaps.
- **Whimsical, Miro, Lucid** pick a kind from a menu of thumbnails with a line each. Taken for (k).

## S1 (k) Kind menu in the Title row

- `frontend/js/diagram-kindbar.js` `mount` (lines 26 to 46): the `.seg.dgm-kinds` well goes; one `button.ghost.small.dgm-kindbtn` (`aria-haspopup="menu"`, `aria-label="Kind of diagram: Flowchart. Choose a kind"`): the kind's sample (20x14) then its word then `ph-caret-down`; below 600 the word hides (the label keeps it), 44 px.
- Where: the named dialog's `.dgm-titlebar` (diagram-embed.js lines 405 to 417), after the field, behind a muted "Kind" span like "Title"; mount replaces an older `.dgm-kindbtn` there (the pane remounts on a kind change, the Title row does not). Without a Title row (Edit diagram, the document's Canvas view): first in `.dgm-dock`, a `.dock-group` hairline after it. Callers stay `diagram-bar.js:119` and `diagram-kinds.js:1031`.
- Menu: `openMenuAtPoint` with four rows, then decorated in this lazy file as `decorateModelMenu` decorates its menu (no eager change, the gzip ratchet has 1 byte): each row gets an inline SVG sample (`createElementNS`, one `path` of `currentColor` strokes per kind, 40x28) and a `.dgm-kind-about` muted line (the KINDS `about` text). The chosen row has `aria-checked`. Under the rows, a muted line when the diagram is not blank: "A new kind starts empty. Undo brings this one back." (`choose` keeps its live line.)
- CSS `frontend/css/diagram-lazy.css`: `.dgm-kinds` rules and the source-view `:is(.dgm-kinds, .dgm-sideways)` (line 1431) become `.dgm-kindbtn`; tokens only.
- Hit: `.dgm-kinds` count 0; the button's rect inside the Title row's; chrome 261 to at most 203 px at 1440 and 329 to at most 277 at 390; picture height 405 to at least 463 at 1440; menu rows at most 56 px, menu inside the window at 390; sample strokes at least 3:1 on the menu surface in both themes (pngpixel). No row of the dialog holds one lone control.
- Tests whose stated intent moved (owner 1661 k): `tests/test_diagram_1679m.py:72-95`, `tests/test_diagram_1107.py:26,119`; mounts and `diagramKindbar` registration stay.

## S2 The new box scrolled into view

- `frontend/js/diagram-overlay.js` `sync` (lines 78 to 93): when a box is created for the selected node (`S.sel`) after the first paint, `box.scrollIntoView({ block: "nearest", inline: "nearest" })`; the figure is the scroller. One line plus a guard for the first paint.
- Hit: at 200% zoom, 10 chained adds (Ctrl+D and Tab chain) leave each new box wholly inside the figure's rect, 10 of 10; no scroll when it is already in view (scrollTop unchanged).

## S3 (m) Both side panels fold to a rail

- In `frontend/js/diagram-split.js` (`wire`, the panel divider already; no new file, no new LAZY_MODULES row). The left panel is the list (Picture and List views) or the source (Source view); the right panel is the picture.
- Open: a `button.ghost.small.icon-only.dgm-fold` (24 px, 44 on coarse) at the panel's top inner corner, `ph-sidebar-simple`, `aria-expanded="true"`, `aria-controls` the panel, `aria-keyshortcuts="["` or `"]"`, title "Fold the list ([)". Folded: the panel is `hidden` and its grid column is a 32 px `.dgm-rail[data-side]` holding the same button with its word set vertical (`writing-mode: vertical-rl`: "List", "Source", "Picture"); the split handle hides.
- Keys `[` and `]` by `event.code` (BracketLeft, BracketRight, so AltGr layouts work) on `S.root`, with the typing guard of `diagram-bar.js` `rootKey`. One of the two always shows: folding the second opens the first; the live line says which and the key.
- Kept: one pref `diagram.fold` (`""`, `"left"`, `"right"`); `diagram.outline === "0"` is read once as `"left"` and cleared. Not mirrored to the notebook (an eager list).
- Removed (replace, not layer): `diagram-bar.js` `OUTLINE`, `paintOutline` and the dock's `.dgm-outline-toggle` (lines 28 to 34, 128 to 136); the `.dgm-no-outline` CSS. `tests/test_diagram_1661b.py:88,97` move to the fold.
- Phone: no rails below 600 (one column). The kinds' pane below 600 is the `.dgm-listbtn` sheet as the flowchart's (`diagram-touch.js` `wire`, line 61).
- Hit: 1440 left folded, rail 32 plus or minus 1 px, picture 905 to at least 1140 px wide; right folded in List view, the list 1174 minus 32; the fold survives a reload; glyph 3:1 on the rail in both themes; sequence picture at 390 from 96 to at least 400 px tall. `docs/DESIGN.md` row 704 (the split recipe) gains the fold, with its lint in `tests/test_ui_recipes.py`.

## S4 (l) Sequence on the picture

- New `frontend/js/diagram-seq-canvas.js`, fetched with `lazyScript` from diagram-builder.js `show` (about line 680) when `S.k?.name === "sequence"`; no LAZY_MODULES row. Pure half under node: `boxes(svg)` reads the `data-et` parts above into `{vb, boxes: [{id: row key, et, x, y, w, h, from, to}]}` (centre-based, as `overlay.math.place` wants; a message's box is its line plus its text, at least 16 drawing units tall); `order(m)` walks `m.steps` in Mermaid's statement order (message, note, block start, divider, block end; `%%` lines skipped; `activate` lines counted) so `iN` names a row. Tests against the login template and one with a loop inside an alt, and one with `activate`.
- `diagram-overlay.js:52`: the guard becomes `S.k && !S.seq`; seq-canvas sets `S.hit` after each draw, so the rings, hover and the selection read from `aria-selected` work unchanged.
- On the picture: a press selects (participant, message, note, box frame); a double press, Enter or F2 opens the `.dgm-rename` field (diagram-edges.js lines 94 to 124; export the field builder) and commits through `kxRelabel`; Delete removes (`kxRemove`); Alt+Up and Down move (`kxStep`); drag a head sideways to reorder participants (a 2 px accent line in the head gap); drag from one lifeline to another adds a message at the gap under the pointer (a rubber line with its arrow; on the same lifeline, a message to itself) and opens its name; a "+" (24 px, `.dgm-gap-plus`) in the left margin of the gap under the pointer opens the kind's grouped Add menu for that gap.
- Hit: 11 of 11 rows of the template selected by a press at their box centre; the rename field's centre within 4 px of the part's, 0 px error after a 100 px scroll; App dragged past Server gives User, Server, App; a lifeline drag from User to Server between messages 1 and 2 inserts at index 1 with the field open and in view; "+" at least 24 px and 3:1 in both themes.

## S5 The shelf: the library on the picture, both kinds

- `frontend/js/diagram-library.js` `build` gains a compact form: a `.dock.dgm-shelf` at the picture's top-left (absolute, inset `--space-3`), six tiles of the kind (sequence: Participant, Message, Reply, Note, Loop, Alt; flowchart: Box, Rounded, Decision, Start and end, Note, Group) as 32 px icon tiles plus a caret for the rest (the grouped Add menu). Each tile keeps `data-obj-grip`, so `diagram-pointer.js` `seed` takes the drag; a press adds after the selection. The toolbar's Add split stays (the keys).
- Drop: the flowchart's is `diagram-canvas.js` `over` (built); the sequence's is seq-canvas `over`: a step tile names the gap by y, from the lifeline nearest x to its right-hand neighbour; a participant names the head gap by x; Loop and Alt wrap the message under the point, else go in empty; the marker is the 2 px line, the caption `dgm-drop-word`. Hidden below 600 and on coarse pointers (the Add sheet stays).
- Hit: the shelf's rect meets the zoom bar's (`.dgm-zoom`) and the first drawn part's at Fit in 0 px (else the picture's top margin grows by the shelf's height); a Message dropped between messages 1 and 2 at App's x inserts at index 1, App to Server.

## S6 Help, docs, blind test

- Guide `diagram-blocks` (`src/tessellate/ai/help_topics_more.py`, near its 1900-char cap: the sentences on the kind row and the Blocks list button are replaced by "Kind in the Title row; [ and ] fold the side panels; drag from the shelf onto the picture; double press any part to rename it"), the dialog help (`diagram-embed.js` about line 400), `tests/test_manual_parity.py`, CHANGELOG (both), CODEMAP, INBOX 1661 (k) (l) (m) fixed lines.
- Blind tester, left panel folded: (a) a sequence of three participants, four messages, a note and an alt; (b) a flowchart with a decision and two labelled branches. Each step: `scripts/gate.sh --staged`, targeted tests `-p no:randomly -n 2`, `tests/test_static_compression.py`, `tests/test_complexity.py` (15 per function).

## Cut

- Converting content between kinds (a new kind starts empty; Undo stays the way back).
- The `.dgm-kinds` well and its roving tab stop; the dock's Blocks list toggle and `.dgm-no-outline`.
- Folding below 600; mirroring the fold to the notebook; touch drag from the shelf (a press adds).
- Mind map and timeline on the picture (next round, after the blind test passes on sequence and flowchart).
- The default fold stays open; flip it to the left folded only after both blind tasks pass (INBOX entry then).

## Log

- done: spec (this file).
- done: S1 262c70da (chrome 261 to 204 at 1440, 329 to 260 at 390; picture 405 to 462 tall; rows 54 px).
- done: S2 (scroll into view; 200% zoom: 0 to 10 of 10 at 1440 Ctrl+D, 10 of 10 at 390 N, none scrolls at 50%).
- done: S3 (fold: rail 32 px, picture 905 to 1136 wide at 1440 with the list folded, list 1136 with the picture folded, kept on reopen; 390 sequence picture 96 to 435). Not built: folding the Source view's text (its folds hide there).
- done: S4 part 1 (press picks 11 of 11 at 1440 and 390, both themes; rename field centre 0 px off; Alt+Down, Delete; a source with activations, a nested loop and a self message 10 of 10).
- next: S4 part 2, `diagram-seq-canvas.js` `wire`: drag a head to reorder, drag lifeline to lifeline to add a message, the "+" in a gap; then S5 shelf (`diagram-library.js` `build`).
