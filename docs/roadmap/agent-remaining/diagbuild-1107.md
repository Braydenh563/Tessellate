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
| DD-6 phone sheet | 390 x 844: dialog 342 wide, foot 153 px (3 rows), dock 18 px outside the dialog, starter picture 240 px, Source under the foot | dialog 390 wide, foot 44 px (1 row), dock 27 px inside, starter picture 434, empty steps and template above the body bottom (707 of 764), Source tab on top and reachable (5 of 5 hit tests), no horizontal overflow in six kinds |
| DD-8a picture keys | picture alt "Flowchart", arrows did nothing on the picture | arrow keys pick the nearest box that way and the live region reads "Check, decision. In from Start, Retry. Out to Done, Retry."; Shift+arrow pans; alt text and aria-description list every box and arrow |
| DD-8 first picture stop | stop 23 from the open focus (five boxes, 1440) | stop 6: only the picked row's swatch, Connect, menu and connector chips are stops; the list foot's twins are not |
| DD-4 rest Undo | a bad line left the note with Go to line only | note is [Undo the last edit, Go to line 4], picture kept (418 px, dimmed), role=alert; one press restores source and picture |
| DD-5 Source pane | Tab left the field, no line numbers, 480 px soft-wrapped field, Ctrl+Z the browser's own, Escape closed the window | gutter and field share top, height (608.4 px) and line height (18 px); scroll lock-step (538 = 538 over 62 lines); Tab and Shift+Tab indent and outdent every selected line; Ctrl+Z steps the shared history (a typed edit is one step); the error line's number is red; Escape moves to the views, the next closes |
| DD-10 empty state | step buttons 113, 133, 131 px wide, rows 43, 32, 43 (two-line words), ticked record kept to the first arrow | 190 px each, rows 60, words one line (18 px); list and frame gone at two boxes, the foot's Connect shows; at 390 buttons 160 px each and the pane 383 = 383 (no scroll) |
| DD-12 title | Done made "Diagram" every time; the PNG was "Diagram builder.png" | a 39 px Title row (50 at 390); PNG "Login flow.png", document "Login flow"; blank is dated ("Diagram 2026-11-07 21:48"), so two Done presses differ |
| DD-13 look | no look choice | ... menu: Hand-drawn look, Clean look; two front matter lines; picture 172 to 176 px wide, SVG 10,160 to 59,754 B; hit boxes found for all nodes; Undo restores. Reduced motion needed no change (`reduced()` already gates the one scroll animation) |
| DD-9a debounce | Source redraw waited 300 ms | 250 ms; typing to new picture 1x [892, 509, 511, 559] to [754, 463, 506, 538] ms, 4x [1060, 731, 786, 823] to [1170, 626, 1027, 865] (noise); open to first block at 4x 758, 443, 144 ms (target under 1,000) |

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

## Round 2 review, fixed (port 8881; `tests/test_diagram_1107c.py`)

| Finding | Before | After |
| --- | --- | --- |
| Review 1: `![[Title]]` could show another diagram | Done kept the typed title as is; `]]`, `|` and `#` went into the link | the window cleans `[ ] | #` as typed and asks the server's list for a free name: runs gave "Login flow", "Login flow 2", "3", "4" |
| Review 2: title outside the discard guard | Escape or Cancel dropped a typed title with no question | the guard asks (confirm shown, 1 of 1) |
| Review 3: `withLook` and an existing `config` | `config: {theme: dark}` gained a second `config:` key | joins inside the braces, clean takes it out; a value it cannot edit is left alone with a toast |
| Review 4 and UX 2: Undo in the error note | shown at the first step; focus fell to BODY | hidden when `canUndo` is false; focus goes to the picture first (FIGURE, inside the dialog) |
| Review 5: arrow pick from a picked arrow | `slice(2)` of an arrow key is no box, so the top left | starts from a box key only |
| Review 6: Add and Connect out of the Tab order | rejected: Tab 2 is "Connect to..." on the picked row and Tab 29 is "Add a box" in the bar; N and C stay in the Keys sheet |
| Review 7: announcement | the duplicate `aria-description` and `alt` is kept (the focusable figure reads the description, the image alt is read only when browsing); the pending `setTimeout` is cleared, so a run of arrows says the last box |
| UX 1: phone Blocks segment | pressed, tree 0x0 | opens the Blocks sheet, tree 343 x 247, the previous view stays pressed |
| UX 3: focus on open at 390 | BODY | the picture (FIGURE, inside the dialog) |
| UX 4: touch hit areas | handle 24 x 44 with a 36 x 56 hit area; divider 12.8 px | handle hit area x -22..22 (45), y -32..32; divider hit area about 44 (hit at 21 px, not at 23) |
| UX 5: look rows | both rows, no state | one row, the look that is not on (Hand-drawn look, then Clean look after the redraw) |
| UX 6: phone Source | 144 px (8 lines) | 262 px, picture 240, no overflow (the kinds row and the sideways offer are hidden in Source) |
| UX 7 and 8 | no row for Left and Right in the bar; Enter on the picked box did nothing | Keys sheet and the diagram-reading topic (1,855 characters) say it; Enter opens the name input with the box's words |

Also fixed: the phone sheet's `border-radius: 0` (round 1, DD-6) was a fifth card radius and turned `tests/test_ui_signatures.py` red; it is `var(--radius-sm)` now (2.4 px, dialog still 390 x 844, no overflow). Found, not mine: `tests/test_zz_probe_tmp.py` (tracked since the composer round 2 review) has an unused `pytest` import, so `scripts/gate.sh` ruff step fails.

Not verified: a screen reader, real touch hardware, the hand-drawn picture render by eye.

## Not built

- DD-5: a Mermaid completion list (needs a keyword table and a menu; the other Source keys are built).
- DD-10: a drawn sample in the blank picture of an empty diagram (the checklist and widths are built).
- DD-11: a lost action after a rename. Not reproduced: 0 lost in 20 trials at 4x CPU with a 500 ms gap (harness `lost.js`: rename, Enter, wait, drag the right handle onto the other box); a guard that dropped the hit map while a redraw was pending was built, measured (boxes 0 during 57 to 672 ms of settling, progress cursor) and left out, because nothing was lost without it and it hides the handles for that time after every edit.
- DD-12: a Versions list of the dialog's history steps.
- DD-13: node and rank spacing (a `config: flowchart: nodeSpacing` front matter did not change the drawn size in the frame).
- DD-9 rest: already there on inspection, not changed: the Create menu and Ctrl+K list "New diagram" (app-features.js, library.js), the New caret menu has a Diagram (.mmd) row, the empty documents list has a labelled New diagram button, and at `(pointer: coarse)` the dock buttons are 44 px (820 touch: no control under 40 px but the shrunk connect handles, 24 x 44). The documents head's New diagram stays an icon with a tooltip.
- DD-9a: pre-warming the lazy modules (open to first block is already under 1,000 ms at 4x).
- DD-15, and the real-model and real-touch checks: only emulated touch was driven; no screen reader was run.
