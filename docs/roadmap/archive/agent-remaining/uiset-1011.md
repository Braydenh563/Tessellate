# uiset-1011: Settings, themes and UI system (ledger 1387 to 1490, 1631)

Owner reports done first: speed opener height (07d447054), track corners (aef9d7633), Recordings empty state (9c1e0d617), the toast stack (4d0cba219), the mono menu row and the font matrix (the font fit commit).

Questions empty state: Notes > Questions uses the `.empty-state` block as Recordings does (emptystates.js: icon centre 0px off, 256px high, action below the title).

Logo motion (owner bug, frozen mark): after merging agent/logo-1011 the mark animates in all five places (logomotion.js: 2 animations on the lock screen, dashboard hero, status bar and chat empty state, 4 on About, transform changing over 500ms in each). App Reduce motion not re-measured; OS reduced motion deliberately leaves the mark moving (02-chat-graph.css). 1410, 1434, 1435: census not done, left open.

Follow-up: the app Reduce motion setting stills the mark (logomotion.js MOTION=reduced: data-motion=reduced, 0 animations, no transform change in all five places). Top-bar census (topbarcensus.js, 13 controls): palette rows 10 to 13 (added Open Settings, Open notifications, Switch space, Quit MemoryMap in settings-panes.js); data-help-for popovers 0 of 13, left by design (top-bar buttons carry tooltips; the Guide covers them).

Owner 2026-10-11, job rows: "Logs at the top left" is read as the top-right corner of the row, on the title line, as a rowActions quiet button (task history: 8 distinct x down to 1, button centre = title centre). Logs filters on the run id (jobruns writes "[run-N] ..." lines to the app log); no lines shows the Bookmarks empty state (joblogs.js).


| id | status | evidence or commit |
| --- | --- | --- |
| 1387 | umbrella | Section head for B87 to B93; its rows are below |
| 1388 | done-already | Settings is two panes plus a sidebar index (DESIGN recipes 775, 776); set.js: 23 nav items, 0 overlaps, 0 clipped at 1440 |
| 1389 | umbrella | UI_MODERNISATION 'Deepened' statistics, utilities, palette: built rows moved to HISTORY (Briefs 89, 90); open rows 3, 4, 6 and palette 2, 4, 6 belong to Briefs 37, 47, 65, 66, 75 |
| 1390 | closed | The oklch(from var(--accent)) assertion holds by design (the accent tints the glow); no fixed-palette test is wanted |
| 1391 | closed | Not reproduced on this head; reopen on recurrence |
| 1392 | closed | The map View menu scrolls under a ~730px window by design (714px of content); nothing to fix |
| 1393 | closed | Not reproduced on this head; reopen on recurrence |
| 1394 | deferred | Deferred by the owner |
| 1395 | deferred | Mind map 25% zoom '+' 5px overlap: MINDMAP_PLAN surface, not driven here |
| 1396 | pointer | Design census for Briefs 57 to 59 (Notes dock 10 items, Tidy badge, 177 off-step controls); owned there |
| 1397 | done-already | settings-reset is in the 'Getting started' help group (help_topics_more.py HELP_GROUPS) |
| 1398 | deferred | maplayouts.js measures the centre topic; a sweep fix in the mind map lane, fails on base too |
| 1399 | decided | Superseded by the later devsize fix (DEVICE_ONLY_KEYS, ai-tools.js): sizes and panel spots stay per device, colours, themes, fonts and motion mirror; the latest dated entry wins |
| 1400 | built | smallButton names an icon-only button by its tooltip and a worded one by its words (WCAG 2.5.3); test_uiset_rows_1011.py (e9bf48384) |
| 1401 | built | refreshEntries refreshes Most used after every write (one fresh GET; the write cleared the read cache) (e9bf48384) |
| 1402 | closed | Each first-run act is a real question; now asked one at a time by the first-run queue (row 1631) |
| 1403 | split | BOOT_CSS_CAP lowered (row 1405); the rows-view meta button and the tool-confirm pair are Brief 57's rowActions sweep (SESSION_BRIEFS 1828) |
| 1404 | done-already | .dash-find has the hover veil (07-whiteboard-misc.css .dash-find:hover, 08-consistency.css dock rule) |
| 1405 | built | BOOT_CSS_CAP lowered from 183,300 to 179,000, the measured 178,530 plus room (test_boot_budget.py) (e9bf48384) |
| 1406 | built | Background jobs: the Import row has a Report button (last-runs carries import_report.latest; settings.js renderJobOverview, 32px high); jobreport.js; the Activity panel translucency at 390 is not re-measured |
| 1407 | built | openSettingRow lands on a row's control (a search for 'accent colour' focuses the active swatch at 1440 and 390, set.js) (e9bf48384) |
| 1408 | built | palettePrefixPicks: stored picks for longer queries count at half weight from 2 typed letters (e9bf48384) |
| 1409 | decided | Kept as is (no stems in the setting words); recorded in the ledger |
| 1410 | not-built | Every rail and top-bar control with a help popover and palette row: M, Brief 41's census; not started |
| 1411 | closed | errors.js at 1440 and 390: 0 errors, 0 layout findings (a record, not a task) |
| 1412 | pointer | 110 controls with no focus change: Brief 57 decision 15 (same as 1430) |
| 1413 | closed | Inventory note (18 overlays plus confirm and tour card); informational |
| 1414 | deferred | Needs the owner (13g middle-button pan never reproduced headless; do not fix blind) |
| 1415 | pointer | Frontend audit leftovers FE-09, FE-10: WORLD_CLASS audit rows; not started |
| 1416 | not-verified | Quit's contrast from pixels and the line-number baseline need a real display |
| 1417 | not-verified | OLED and gamma reading need hardware |
| 1418 | not-verified | Write with AI with a model running needs a model (CLAUDE.md section 4) |
| 1419 | built | Help popovers fade out like menus (.help-popover.hidden joins the exit transition; wireHelpPopover moves home after the exit) (e9bf48384) |
| 1420 | built | Settings sections fade in (CSS only, settings-pane-in on .settings-section:not(.hidden), 0.2s); panefade.js samples opacity 0,0,0,0.77 over 240ms |
| 1421 | decided | 444 decision 10: Tools and Appearance stay indexed, not split (the index is the recipe); closed |
| 1422 | not-verified | Doc-focus panels 720 to 819px not driven in a sweep |
| 1423 | built | scroll-padding-block: var(--ring-room) now covers .library-view-section (was .tab-page, .dash-body) (e9bf48384) |
| 1424 | built | refreshJobRuns stops when signed out and re-arms only with a token (no 401 after a lock) (e9bf48384) |
| 1425 | not-verified | tests-e2e shell.spec.js handoff test: Playwright's runner not run here |
| 1426 | closed | Not reproduced on this head; reopen on recurrence |
| 1427 | pointer | Notes dock wrap 1280 to 1640 with the rail open: Brief 41 density |
| 1428 | deferred | Deferred by the owner (Brief 32) |
| 1429 | done-already | tour.js tourReveal: the card holding the target takes .tour-reveal, which the hover rules match (00-tokens-shell.css) |
| 1430 | pointer | Same as 1412: Brief 57 decision 15 |
| 1431 | closed | Row height 46.8px set by the Connect button's target floor; left by decision |
| 1432 | closed | Rule 14: Health stays in Settings, About; reach is the palette and the status bar |
| 1433 | not-verified | Right-click menus, keyboard-only acts and two-step pickers are outside the crawl |
| 1434 | not-built | #select-btn and #notes-filter-menu dock words clipped by the label-to-icon collapse at 320 to 1024: the font matrix sweep reports them; Brief 41 |
| 1435 | not-built | #notes-tidy 4px and #tab-notes .layout 4px: as 1434 |
| 1436 | not-verified | Dashboard overflow selectors not named by the census; the font matrix sweep names them now |
| 1437 | pointer | Crawl: 16 destinations with no palette row: Brief 41 / palette rows |
| 1438 | closed | Method note on the crawl; informational |
| 1439 | pointer | acts.palette_rows has no caller: CHAT_PLAN Brief 66 (palette from the registry) |
| 1440 | pointer | Settings synonym table is a hand table: CHAT_PLAN filters work |
| 1441 | skipped | The rename (brief: skip the rename) |
| 1442 | pointer | Decision 1 panel padding and gutter: Brief 41 density |
| 1443 | pointer | Base failures test_finder_star_790, test_has_invalidation: mergetrain lane |
| 1444 | done-already | Hover-ground lint and sweep landed (ownerfix3); the owner's element not found |
| 1445 | closed | Known limit of the class-level lint; noted |
| 1446 | not-verified | Dark and 390 beyond the five sweeps; font matrix now adds both themes at 390 |
| 1447 | not-verified | 851 rows view at 390 and the tick's dark colours |
| 1448 | skipped | LAN and phone (brief: skip) |
| 1449 | done-already | Each log record has its own copy, Copy traceback and 'Copy N shown' (BACKLOG text describes the built state) |
| 1450 | closed | Measured judgement: the JSON is not worth compressing |
| 1451 | built | Settings, Themes, Surprise me (#theme-surprise in settings-controls.js); themepreview.js sweep: picks a theme other than the active one, stored value set |
| 1452 | built | Hover or keyboard focus on a theme card previews it (themePreview, read ahead of the manual layer, never stored); themepreview.js: preset changes while hovered, localStorage untouched, restored on leave |
| 1453 | deferred | A decision for the owner, not a build |
| 1454 | pointer | Screen-reader pass: BACKLOG section 115 row 4, axe sweep; not started |
| 1455 | not-built | Opt-in retention rules: L, needs a decision and a backend job |
| 1456 | deferred | Saved swatches panel: M, spans swatchPicker, whiteboard and categories; left for the next PR |
| 1457 | pointer | Memory as a surface: PLAN A3; not started |
| 1458 | done-already | BACKLOG section 110.2: the gallery kebab closes on capture; fixed then |
| 1459 | done-already | BACKLOG section 110.2: zero flex basis on the status span; fixed then |
| 1460 | closed | Suite size note; informational |
| 1461 | built | The welcome's setup slide offers 'Bring in your notes' on an empty notebook: it closes the welcome and opens Settings, Import & export at Import files (e9bf48384) |
| 1462 | deferred | Guarded in tour.js with Tour: log lines; open until the owner's next run |
| 1463 | skipped | The composer's token window (brief: skip the composer) |
| 1464 | skipped | In-text reference hover is the chat composer lane |
| 1465 | skipped | The composer's token pill (brief: skip the composer) |
| 1466 | deferred | Deferred by the owner (Brief 32) |
| 1467 | pointer | Brief 92, the whole-app pass; first-run part built here (row 1631) |
| 1468 | done-already | Settings nav: 0 overlaps (set.js) |
| 1469 | done-already | Every '?' is .graph-help-toggle at var(--radius-md), not a circle (03-dashboard-widgets.css, the owner 2026-10-10 quoted there) |
| 1470 | pointer | 'No vertical gap': surface not named; Brief 41 census |
| 1471 | pointer | Major polish of every dock and menu: Brief 41; the menu row fit (mono) is one part, built here |
| 1472 | decided | Recommendation: build only if the census shows Quick access is hard to find; not built |
| 1473 | done-already | Settings, Background jobs (#job-runs-group) lists each run with its log |
| 1474 | pointer | INBOX 789 one hover for every button: built as DESIGN 'One hover for every button'; the ratchet is in test_ui_recipes |
| 1475 | pointer | 809 Help 'Welcome and tours' redesign: L, Brief 92 |
| 1476 | done-already | Settings packages rows aligned: centres within 2px at 1440 (set.js) |
| 1477 | done-already | Help accordion rows 0 gap with dividers; group heads 16px and 8px (set.js) |
| 1478 | pointer | Laptop chrome share 36%: Brief 41 density |
| 1479 | done-already | Support bundle, Settings, Logs (#logs-bundle) |
| 1480 | done-already | #ai-status-popup opens on hover and click |
| 1481 | done-already | Group heads follow recipe 780 (--text-lg, 650) |
| 1482 | done-already | #conv-empty is the .empty-line small-panel recipe |
| 1483 | not-verified | The Windows restart error needs the Windows app |
| 1484 | built | Settings, Help, Credits (and the Guide topic credits): a fold drawn from docs/THIRD_PARTY.md via frontend/credits.json (scripts/build_credits.py; test_credits.py) (e9bf48384) |
| 1485 | decided | As 1399 |
| 1486 | built | errors.js takes THEME, FONT and SLOW; fontmatrix.js runs both themes; FAULTS=1 not run here |
| 1487 | closed | Known limits of the census script; noted |
| 1488 | closed | Known limits of codemap.py; noted |
| 1489 | closed | Heuristic noted in measure-settings-help.py |
| 1490 | not-built | Decision 43's rate editor: the rates are read by the composer's call (brief: skip the composer) |
| 1631 | built | First-run queue (onboarding.js firstRunTurn): welcome, recovery, console, updates, one at a time after toasts (0076136aa) |
