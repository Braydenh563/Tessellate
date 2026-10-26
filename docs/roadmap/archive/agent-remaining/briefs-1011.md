# briefs-1011: SESSION_BRIEFS triaged, then the open briefs built

Port 8789, data dir `/home/user/.mmscratch/briefs-data`. Left out (owned elsewhere): 27 (phone), 88, 90, 95, 97, 101b, 101c, 102 (LAN), 104, and undo / Settings About work.

## Triage, 2026-10-11

| Brief | State | Evidence |
| --- | --- | --- |
| 2 consistency lints | built | `tests/test_consistency_contract.py` (surface in surface, one filled button, quiet meta chips, transparent menu items); `DEFAULT_SHORTCUTS` (settings-wiring.js:904) with `test_frontend_shortcuts.py` |
| 3 prefs, api, innerHTML | partial | reads, `api.upload/stream`, `test_no_bare_fetch.py`, `test_no_innerhtml_interpolation.py` built; 283 `setItem/removeItem` in 49 files left |
| 4 Settings, paragraphs | partial | `#settings-nav` built; `help-audit/count.py` TOTAL 28, countjs 1+1 |
| 5 Timeline 1 and 2 | built | TIMELINE_PLAN Phases 1 and 2 built 2026-09-13; `timelineRow` (timeline.js:115) |
| 6 pagination, scheduler | built | `api/paging.py` on 18 routers; F6 done 2026-09-21 (HISTORY 5409), scheduler judged unneeded |
| 8 `[[` and rail | built | WORLD_CLASS D2 built 2026-09-27, HISTORY "D2 connections rail" |
| 9 job runtime | partial | B2 built 2026-10-04 for the pool's kinds; other kinds and the panel left |
| 10 Library card, widget frame | built | D1 state 2026-10-05 (one frame over `DASH_WIDGETS`); D4 absorbed by UI 8 to 11 |
| 13 verifier | built | built 2026-09-12; left list in `archive/agent-remaining/brief-13-harness.md` |
| 14 docs condensed | superseded | HANDOVER capped at 600 by `test_plan_hygiene.py`; the Fable window it wrote for is gone |
| quarter's briefs | superseded | every item is a row in its plan (GRAPH, DOCUMENTS, MINDMAP, WORLD_CLASS B4, B6, B8, D5, D6, D9, F12) |
| 16 docs refined | built | expansion files gone; `test_no_em_dashes.py` covers docs and root md; README in the brief's shape |
| 17 launchers | built | `--doctor`, `--shortcut`, `--logs` in start.sh/bat; `launch_status.py`; `start-desktop.sh`; uninstall `--dry-run`, `--export`; `test_launcher_scripts.py` |
| 18 open scope | built | its INBOX items (66 to 98) all resolved; sections B to G are plan rows |
| 25, 26, 29, 31 | built | TIMELINE 1 to 4, CHAT 2 and 3, GRAPH local map (2026-09-13), SKILLS Phase D (2026-09-13) |
| 28, 30 | built as briefs | left work is DOCUMENTS_PLAN Phases 6 and 8 and MINDMAP 12.2 and 12.3 rows |
| 32 templates | built | BACKLOG 4b, `whiteboard-templates.js`, `wbSaveBoardAsTemplate` |
| 33 rest of WORLD_CLASS | superseded | carried out as Briefs 35 to 104 |
| 34 characters | partial | rows 1 to 3 and most of 6 built; character files shared with Brief 88 (merging), so not taken here |
| 35 to 42 | built | triage-1010, boardmap-1010, chatui-1010, graph-1010, engine-1010, filing-1010, research-1010, density-1010, docs42 ledgers; HISTORY moves |
| 43 expert audit | built | BACKLOG "Expert audit, 2026-10-10" |
| 44 draw.io | built (part 1) | WHITEBOARD "The draw.io programme"; part 2 is its expansion row 5 |
| 45 structure | partial | part 1 is WORLD_CLASS 24; part 2 open (census-1010) |
| 46 to 55 | built | HISTORY moves for 47 to 55; 46 measured in WORLD_CLASS 25.2 |
| 56, 57, 60 | built | UI 13.0 measured; 13a HISTORY; 26.0 and 26a HISTORY |
| 58, 59 | open | `08-consistency.css`, `10-responsive.css` still exist; 13c rows open |
| 61, 62, 63 | open | `routes_whiteboard.py` 5,808 lines; no `src/memorymap/data/`, no `test_import_time.py` |
| 64 to 75, 76 to 84 | built | HISTORY moves per brief; `test_one_reader.py`, `test_vendor_utilisation.py`; WORLD_CLASS 28.6 T0 |
| 85 launch splash | open | splash.ps1 still a WinForms ProgressBar with four footer buttons |
| 87 voice | partial | step 1 in ANALYSIS "Vendor candidates, 2026-10-11"; step 2 open |
| 92 whole-app pass | partial | (c) in 95, (e) 57; (a) tour E2E and (b) element comparison open |
| 93, 94, 96, 99, 100, 103 | built | ownerfix3, meaning94, voiceup, scan, graph100, chattime merged |
| 98 goals and lists | open | no goals or lists model, route or surface |
| 101a | built | room101 merged |

## Build order (SESSION_BRIEFS order)

3, 4, 9, 34 (skipped, 88's files), 45, 58, 59, 61, 62, 63, 85, 87, 92, 98.

## Log
- done: b569ca38f triage.
- done: Brief 3 (writes through prefs; see next commit). next: Brief 4, index.html paragraphs (help-audit count.py TOTAL 28).
- done: Brief 4 (count.py 28 to 3, the 3 are aboutkit's Settings, About; countjs 0). next: Brief 9, B2 rest (pull, reindex, pass, autonomous onto the durable pool; the panel on the stream).
- found, not fixed: `help-popovers.js` fails 6 triggers it cannot click (`#skill-tools-help`, `#skill-verify-help`, `#custom-css-help`, `#import-app-help`), none touched here; `test_background_registry` and `test_flaw_class_lints` fail on the base for `core/lanserve.py` and `routes_recordings.py` threads (the phone agent's area).
- done: 962d7b7cb Brief 4. Brief 9 (B2 rest): pull, reindex, pass, autonomous durable on the pool; the panel on `/jobs/stream`; left in the brief: the folder import. next: Brief 45 part 2 (3 dead defs removed; the splits deferred while canvas agents hold whiteboard.js).
- done: 139f914d7 Brief 9. Brief 45 part 2: 3 dead defs removed; splits and the duplicated blocks deferred (wbs, docs, chatmind hold the files; reason in the brief). next: Brief 58 and 59 deferred on the same ground (uiset and house1 hold 08 and 10 CSS, index.html); Brief 61 services in progress.
- done: c16b51937 Brief 45 part 2. Brief 61: routes_whiteboard 5,808 to 1,438 lines, routes_files 4,028 to 1,905, two services; wording lints now read the services. next: Brief 63 (embedder idle unload, decision 62; the runners' state machines and the tools split deferred, see the brief).
