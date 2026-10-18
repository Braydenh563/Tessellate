# Owner bug document, 2026-10-18 (INBOX 1300): triage and status

The verbatim text is INBOX 1300 (C01 to C36) with its triage block. Two Haiku
audits reproduced each bug in the app (ports 8791, 8792). A row is **open**,
**fixed** (commit), **not reproduced**, or **placed** (plan named).

| Item | Rung, agent | Status | Evidence |
| --- | --- | --- | --- |
| C10 statistics in quick access | S, fixes1 | fixed 8430914 | `quickCatalogue()` now returns `act:statistics` beside `act:captions` |
| C09 attach list Enter | S, fixes1 | fixed 1ce15c0 | two ArrowDowns then Enter: row 1 checked, focus on it, panel open; Enter in search is Done |
| C13 table plus off centre | S, fixes1 | fixed 300e718 | plus drawn in CSS; ink centre 0.875 css px low at 4x before, 0.25 (one device pixel) after |
| C17 frame hint becomes header | S, fixes1 | fixed 9a5e195 | hint edit opens its own text; edit then Ctrl+Z restores it; click-off with no change keeps it |
| C31 link kind cannot be cleared | S, fixes1 | fixed 4487b44 | test only; sheet not driven in the app |
| C32 undo shows nothing | S, fixes1 | fixed ae8174e, 4b45f60 | muted: board Undo shows "Undone: last change on this board"; document path test only |
| C35 missing package toast, no link | S, fixes1 | fixed 4b45f60 | Translate notice: Open Packages click lands `extra-row-translate` at top 371 of 900 |
| C03 right-drag pan | S, fixes2 | open | button 2 refused `whiteboard.js:91`, menu `:8640` |
| C12 sticky panel header | S, fixes2 | open | `.dialog-head` static in `.stats-card` |
| C25 Help scroll lag | S, fixes2 | open | 4x CPU: median 33 to 50 ms a frame, 1954 nodes |
| C15 typo question answered from notes | S, fixes2 | open | "Wat cna u do??" read right, then note citations |
| C02 splash rows grow | S, fixes2 | open | `scripts/splash.ps1:394` uncapped; Windows only |
| C23 go-key prefix | S, fixes2 | open | decision: prefix `t`, Timeline second key `i`, `m` alias one release |
| C01 throw lands, peek then fall | O, design | open | `avatars.js:5706`, `:6098` |
| C19, C20 companion layer and size on boards | O, design | open | band z 44 over Format z 25; WHITEBOARD step 8 |
| C05 slash commands below fold | O, design | open | first command at 444 px in a 386 px menu |
| C29 popup Sources disclosure | O, design | open | `chat-agent.js:2220`, no marker |
| C33 notification stack | O, design | open | four toasts 186x205 px |
| C21 theme preview revert and bar | O, design | open | `settings-controls.js:2877` |
| C22 shortcut chip Change | O, design | open | `settings-wiring.js:1386` |
| C06, C07, C08 reply cards, preview, fold, calculator | O, design | open | `/calc` `slash_more.py:200`; peek `capture-ask.js:1412` |
| C11 graph node hover card | O, design | open | `graph-canvas.js:3753` title tooltip only |
| C27 graph popup props button | O, design | open | `index.html:4448` |
| C28 reply reveal animation | O, design | open | chat 0.2 s fade only; guide streams words |
| C30 lightbox controls | O, design | open | `lightbox-view.js` |
| C34 recorder panels | O, design | open | `.meeting-stage` radius 0, `meetings.js:922` |
| C36 timeline tick labels switch | O, design | open | `timeline-ticks.js` |
| C14 composer and model badge | O, design | open | `chat-attach.js:2430` byline |
| C18 paper swatches as dropdown | O, design | open | `index.html:7506` |
| C04 UML, ERD, wireframe sets | plan | placed | WHITEBOARD_PLAN |
| C16, C26 composer variety, greeting sub line | plan | placed | CHAT_PLAN; `composer_voice.today_line` unused |
| C24 Logs panel scroll | none | not reproduced | equal heights at five sizes; Settings nav overflow placed in WORLD_CLASS row 32 |
