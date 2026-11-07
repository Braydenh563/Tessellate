# Diagram build 1107: built from the dive, and what is left

Source: `diagram-dive-1107.md` (rows DD-1..15). Measured in the running app (port 8821), before and after.

## Built (one commit per row)

| Row | Before | After |
| --- | --- | --- |
| DD-1 kind bar in New diagram | Sequence, Mind map, Timeline changed the source but the pressed button and dock stayed Flowchart | pressed button and dock follow in under 1.2 s; one Undo restores the flowchart |
| DD-2 docks | docks 543/124/199 px, 1 overlapping pair each, dialog 225 px too wide | dock 46 px, 0 overlaps, overflow 0 at 1440 and 1000; 62 px, 0 overlaps at 390 |
| DD-4 drawing error | picture blanked, no alert, tall-chart offer stayed | last good picture kept at opacity 0.4, `data-line`, role=alert once per new error, Go to line button, banner cleared |
| DD-3 starter and Tab chain | 2 clicks, 19 keys, 1 drag, unconnected | opens on a 3-box starter, box A focused; 3 connected boxes in 1 click and 11 keys; Tab adds a joined box, Shift+Tab selects its source, F6 leaves the blocks; Clear in the ... menu |
| DD-7 help | `?` only with a block focused | `?` opens the keys sheet from 5 of 5 focus targets, not in a text field; Keys chip 82 x 32 (1440), 82 x 44 (390); ? popover with the Guide offer; keys in tooltips; Guide and parity test updated |
| DD-8 order | Add a box was tab stop 8 | kind bar is one roving stop: Add a box is stop 5, 3 Shift+Tab from the open focus. DOM order was already head, kinds, dock, panes, footer |
| DD-14 handle click | a click armed the handle and waited for a second click | a click adds a joined box and focuses its label input (3 to 4 boxes); drag still connects; Enter on a handle still arms |
| DD-9 small part | dock 44 px at coarse already (7 of 7 buttons 44 x 44 at 390 touch) | now linted; "diagram" in Ctrl+K lists New diagram first and Enter opens the window |

## Review of the build (port 8821, measured before and after)

| Finding | Before | After |
| --- | --- | --- |
| Size cap, 3 tests red | builder 12,824 B gzipped | 12,000 B (python gzip 9); `failure` in diagram-picture.js, Tab and F6 in diagram-bar.js `chain`; cap not raised |
| 1596 test red | asserted the old call | points at `picture.failure`, and also asserts kept picture, stale class, alert vs status, sideways offer hidden |
| Clear on a non-flowchart | switched the kind | starts the pane's own kind (`STARTS[kindOf(...)]`) |
| Escape over the Keys sheet | sheet stayed, 5 open/close cycles stacked 5 | closes (sheets 1 to 0, focus back on the block); the sheet only yields to a confirm opened after it |
| Tab trap | 44 Tabs from open: boxes 3 to 25, no stop outside the blocks | 40 Tabs: boxes 3, stops cross picture, handles, footer, head and back; Tab adds only on the last box, Shift+Tab with no parent leaves; the blocks line, Keys chip and Guide name F6 |
| Mobile 390 | dialog scrollWidth 359 vs 340; More right edge 367 vs body 349; picture 96 px in 3 kinds | 340 = 340; More right 338; picture 240 in all four, pane below it (no overlap) |
| Embed card on Notes | "Nothing called ... yet" (reload too) | "<name>: open the diagram"; the first miss fetches the documents once and redraws |
| Ctrl+Enter | nothing | keeps the diagram from anywhere in the window; in the Keys sheet and the Guide |
| Focus after a kind press | BODY | the pressed kind button |

Judged not defects:

- Esc closing the builder: `finish(false)` asks "Close without keeping your changes" whenever the source differs (`mayDiscard`); it closes silently only when nothing changed.
- Tab order "Add box is the 22nd stop": measured from F6, which lands on the picture, so it counts the whole run to the footer and round. From the open focus Add a box is 3 Shift+Tab (DD-8, above). A picture node is still not a stop (DD-8a, below).
- Focus on open stays on the first box: the starter's Enter-to-name path (DD-3) depends on it; the trap is gone, so it no longer strands the user.

## Not built

- DD-4: an Undo the last edit button on the error note, and a true gutter marker (the source box has no gutter; the line is exposed as `data-line`).
- DD-6: the footer is still three rows at 390 (153 px of 844).
- DD-8: first picture node at most 6 stops (it is stop 26 at 1440; each block row has about 4 stops: needs the list as one roving tree).
- DD-5, DD-6 (footer still three rows at 390: 153 px), DD-8a, the rest of DD-9, DD-9a, DD-10..13, DD-15.
- Real-model and touch-device checks: only emulated touch was driven.
