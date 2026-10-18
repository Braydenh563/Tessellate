# Owner bug document, 2026-10-18 (INBOX 1300): triage and status

The verbatim text is INBOX 1300 (C01 to C36) with its triage block. Two Haiku
audits reproduced each bug in the app (ports 8791, 8792). A row is **open**,
**fixed** (commit), **not reproduced**, or **placed** (plan named).

| Item | Rung, agent | Status | Evidence |
| --- | --- | --- | --- |
| C42 composer reply text lost after restart (first, data) | S, next free Sonnet | fixed 873f8fd | fresh data dir, 'yo wassup :)' as first message: stored content empty in 1 of 2 runs before, 0 of 4 after (scratchpad/ui-sweeps/c42.js) |
| C10 statistics in quick access | S, fixes1 | fixed 8430914 | `quickCatalogue()` now returns `act:statistics` beside `act:captions` |
| C09 attach list Enter | S, fixes1 | fixed 1ce15c0 | two ArrowDowns then Enter: row 1 checked, focus on it, panel open; Enter in search is Done |
| C13 table plus off centre | S, fixes1 | fixed 300e718 | plus drawn in CSS; ink centre 0.875 css px low at 4x before, 0.25 (one device pixel) after |
| C17 frame hint becomes header | S, fixes1 | fixed 9a5e195 | hint edit opens its own text; edit then Ctrl+Z restores it; click-off with no change keeps it |
| C31 link kind cannot be cleared | S, fixes1 | fixed 4487b44 | test only; sheet not driven in the app |
| C32 undo shows nothing | S, fixes1 | fixed ae8174e, 4b45f60 | muted: board Undo shows "Undone: last change on this board"; document path test only |
| C35 missing package toast, no link | S, fixes1 | fixed 4b45f60 | Translate notice: Open Packages click lands `extra-row-translate` at top 371 of 900 |
| C03 right-drag pan | S, fixes2 | fixed e7b64b0 | `wbrightpan.js`: right-drag 150 px pan, 0 menus after a drag, 1 after a click, card press 0 px |
| C12 sticky panel header | S, fixes2 | fixed af73696 | `dialogheadsticky.js`: Statistics head 17 px at rest and after 400 px scroll (was -383) |
| C25 Help scroll lag | S, fixes2 | fixed da029b4 | `helplag.js` 4x CPU: median frame 33.3 to 16.7 ms (General 16.7); Paint 2196 ms to under 600 ms |
| C15 typo question answered from notes | S, fixes2 | fixed e600092 | route test: capability reply for "Wat cna u do??"; render checked (4 paragraphs, 2 bold, no stray stars) |
| C02 splash rows grow | S, fixes2 | fixed 03b6bf4 | height capped at MAX_ROWS (static test); not verified on Windows |
| C38 splash flicker | S, fixes2 | fixed 03b6bf4 | double buffered, layout and labels written only on change; not verified on Windows |
| C23 go-key prefix | S, fixes2 | fixed bfcb7f5 | `gokey.js`: t guide opens, t t closes, t i Timeline, m d Dashboard, t n Notes |
| C01 throw lands, peek then fall | O, design | fixed | tucked frames during the fall 43 of 43 to 1 of 44, sink 38 to 0 px (`peektravel.js`) |
| C19, C20 companion layer and size on boards | O, design | fixed | over the Format panel: the companion drew on top (band z 44) to the panel on top (z 9 on the canvas); scale at zoom 0.5: 1 to 0.5; wander chance on a board 0.35 to 0.1 (`canvas1300.js`). WHITEBOARD step 8 (layer order) not a dependency, left |
| C05 slash commands below fold | O, design | fixed | first command row 443 px down a 384 px menu (unseen) to 27 px, active; ArrowDown to the next command (`slash1300.js`) |
| C29 popup Sources disclosure | O, design | fixed | caret e136 -90deg shut, none open; rail 1px at 14 px; shut at rest in popup and chat (`sources1300.js`) |
| C33 notification stack | O, design | fixed | 5 live toasts: 3 cards 250x205 px at rest -> 1 card + "+4 more" 181x94 px; hover or focus opens 3 + "+2 more" (`toast1300.js`) |
| C21 theme preview revert and bar | O, design | fixed | hover 900 ms on card or eye: no preview; eye: notice 254x81 "Previewing the X theme." Apply/Cancel; undone on Cancel, eye again, section switch, close, hidden tab, Escape; Apply keeps it (`theme1300.js`) |
| C22 shortcut chip Change | O, design | fixed | 32 of 32 rows carry a 16 px pencil 10 px after the keys, muted at rest, accent aimed at, x while capturing; no row or chip overflows at 1440 or 390 (`shortcut1300.js`) |
| C06, C07, C08 reply cards, preview, fold, calculator | O, design | open | `/calc` `slash_more.py:200`; peek `capture-ask.js:1412` |
| C11 graph node hover card | O, design | open | `graph-canvas.js:3753` title tooltip only |
| C27 graph popup props button | O, design | open | `index.html:4448` |
| C28 reply reveal animation | O, design | open | chat 0.2 s fade only; guide streams words |
| C30 lightbox controls | O, design | open | `lightbox-view.js` |
| C34 recorder panels | O, design | open | `.meeting-stage` radius 0, `meetings.js:922` |
| C36 timeline tick labels switch | O, design | fixed ae7fb1c | the c36 sweep toggles the switch and counts the tick labels; test_timeline_ticks_switch.py |
| C14 composer and model badge | O, design | open | `chat-attach.js:2430` byline |
| C18 paper swatches as dropdown | O, design | open | `index.html:7506` |
| C37 graph box titles clipped, no ellipsis; nodes all one size | O, design batch 2 | open | a question is a bug report: size by weight (links or uses) and a label line-clamp with ellipsis |
| C39 timeline opens on empty future days | S, next free Sonnet | fixed 5049124 | the c39 sweep measures Today's row top against the feed top on open and after the Today button |
| C40 recording transcript lines cannot be copied | S, with C34 | fixed f749f62 | the c40 sweep copies a line, a Shift range and all lines; test_transcript_copy.py |
| C41 force graph messy | O, graph batch with C11, C27, C37 | open | screenshot: labels collide, edges cross clusters, duplicate titles unexplained; label collision avoidance, cluster separation, edge bundling or fade, measured overlap count before and after |
| C43 categories sidebar messy, sections not collapsible | O, design batch 2 | open | screenshots: nested scrollbars plus a blue bar on the outer one, list clipped mid-row, near-duplicate "Courses & Study" / "Courses \| Study", empty categories; collapsible sections with remembered state, one scroll container, merge offer for near-duplicates, hide empty |
| C44 live view section break overlaps gutter numbers | S, next free Sonnet | fixed 216ac23 | the c44 sweep measures the gutter row height against the rule line; test_live_rule_line_height.py |
| C04 UML, ERD, wireframe sets | plan | placed | WHITEBOARD_PLAN |
| C26 greeting sub line composed and rotating | S, fixes5 | fixed HASH26 | `/insights/today-line` wired to `renderDashSubmessage`; 13 distinct lines in 20 seeded draws (test_composer_voice.py); C16 stays in CHAT_PLAN B41 |
| C24 Logs panel scroll | none | not reproduced | equal heights at five sizes; Settings nav overflow placed in WORLD_CLASS row 32 |
