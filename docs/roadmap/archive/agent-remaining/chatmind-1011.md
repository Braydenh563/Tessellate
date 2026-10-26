# chatmind-1011: OPEN ledger rows 544 to 660 and 700 to 791

Brief: every S and M row built, done-already or truly blocked; L rows deferred-next-PR.
Status words: done (commit), done-already (evidence), composer agent, pack agent, blocked (why), deferred-next-PR (L).
No real model in this sandbox: `scratchpad/llama-dev.sh check` finds neither llama-server nor a GGUF, so real-model rows are blocked.

| id | status | evidence or commit |
| --- | --- | --- |
| 544 | done-already | AGENT_SKILLS_REFORM Phase D built 2026-09-13 (HISTORY); mechanism sound; breadth is row 598 |
| 545 | pack agent | pack-1011 row 319 builds MCP resources, prompts and `--mcp`; items 1-3, 5, 7 already in mcp_server.py |
| 549 | blocked | a caveat; the chips' model choice needs a real model (none here) |
| 550 | done-already | a rule for the next head, held by the panel-head lint; nothing to build |
| 551 | composer agent | the Guide's no-model answer wording (help_chat.system_answer) |
| 552 | done | search-suggest.js SEARCH_SUGGEST_LISTS, searchSuggestTitleHits; tests/test_search_suggest_lists.py. Measured (sugg552.js, "gar" in Documents): 2 "In this list" rows, list 299px under a 262px box at 390, 446 under 408 at 1440, no horizontal overflow at either |
| 553 | done | activity.StreamNarrator reads thinking, delta and item (Guide, drafting, review); chat and agent turns not announced is decided (routes_tasks.WATCHED_KINDS: a watched turn is listed, never announced) |
| 554 | done-already | meetings marks use rowActions (meetings.js:1731); tag and category managers fold every action into one ⋮ per row and the count button is Show notes; the suggestions inbox's accept is the card's purpose, not a repeated row action (decided here, standing order 3) |
| 555 | done | utilities.SEVERAL_ZONES; tests/test_utilities_zones.py |
| 556 | done | chat-attach.js chatTidyTyped; tests/test_chat_stray_keys.py |
| 557 | done | skills.held_back_reason checked in tools.validate_run_skill; tests/test_skill_fixtures.py |
| 558 | done | routes_settings._merged_list: skills, personas, templates merged by name; Undo sends replace_lists; tests/test_settings_rows.py. Desktop save path: blocked (needs the pywebview window) |
| 559 | done-already | help_chat.py:1268 board-library-saving and :1388 whiteboard-selection are already split topics |
| 560 | deferred-next-PR | measured 137 tab badges with no `target` (library 60, notes 44, chat 11, others 22): L, not S |
| 562 | done | starter_acts tag_open, save_answer, open_links, open_board, open_note for documents; tests/test_starter_acts_tabs.py |
| 561 | done-already | measured (remind561.js, 1440): "remind me to call the dentist tomorrow at 9" leaves one p "Done: remind you tomorrow at 9: call the dentist." in the bubble; innerText holds it once |
| 563 | done | Python: _mm_debug runs _mm_tests under the debugger (runcall), test rows and totals; tests/test_run_debugger.py. JavaScript: deferred-next-PR (L: the harness is async with spread, both refused by the ES5 stepper; needs an ES5 harness inside JS-Interpreter) |
| 564 | done | chat-attach.js chatTurnObjects puts each answer's note titles on its turn; ChatTurn.objects; reading._follow_other matches a title holding the named subject; tests/test_spoken_followups.py |
| 565 | blocked | needs the Guide run against a real model to read the fallback's log line (none here) |
| 566 | done | routes_map_from_notes.map_from_note_entry and POST /whiteboard/maps/from-note/{id}; tool map_from_note (registered, verified, cued); a note's ⋮ menu, Make a mind map; tests/test_ai_mindmap_tools.py. "Summarise this board" was already read_whiteboard |
| 567 | done | phone-shell.js phoneSheetDialogs stamps the eight as sheets below 600. Measured (sheets567.js, 390): all eight left 0, width 390, bottom 844, radius 0 (history and connections were 359 wide, 16px in); 1440 unchanged (centred, 8px) |
| 568 | done | phone-shell.js dockItemCount, DOCK_FOLD_PAST 7: arrange folds past seven at every width; Select and Refresh marked data-fold-narrow; DESIGN dock recipe. Measured (docks568.js): DOCKS |
| 546 | done-already | Phase 4 built 2026-09-12 and its harness items closed 2026-09-20 (HISTORY) |
| 548 | blocked | the Phase D claim needs a model to stall and be fixed (none here) |
| 569 | blocked | the chat screenshot needs a real model's answer (none here) |
| 573 | blocked | #chat-model-panel opens only with a model connected (none here) |
| 599 | done-already | mcp_server.CHAT_ONLY plus ends_turn withheld from offered_tools |
| 600 | done-already | mcp_server._clean_label strips `ph:` tokens |
| 601 | done-already | mcp_server._annotations: readOnlyHint, destructiveHint, openWorldHint |
| 602 | pack agent | version negotiation exists (SUPPORTED_PROTOCOLS); resources and prompts are pack-1011 row 319 |
| 603 | done-already | embedder lazy (EmbeddingService._st_model); initialize answered with no weights load on stderr |
| 604 | pack agent | pack-1011 row 319: `--mcp` built there; `/mcp` HTTP deferred there (needs a client key) |
| 605 | done-already | Settings, Tools MCP snippet (#mcp-config-snippet, settings-controls.js) |

done: f0f9d97 rows 555 to 557; 5fffcea rows 552 to 554, 558; 99b27e7 row 562. next: rows 559 to 573 (B27).

## Mind map (700 to 791)

| id | status | evidence or commit |
| --- | --- | --- |
| view-menu | done | coordinator item: #wb-view-menu two `.wb-menu-col` columns (Panels, Zoom; Canvas, Map), no printed heads, one column below 600; Full screen a row only below 820 (the top bar's button is beside View above). Supersedes INBOX 793's one column (the 450px ceiling is the sweep's). Measured (mapviewmenu.js): VIEWNUM |
