Counts, re-checked 2026-11-11 at head 5fbaedf23, updated after the decision agents: fixed 20, stale 44 (pointer in the row, details in v1028-1.md to v1028-4.md), open 6 (each names its blocker), unsure 72. Source: audit-1028-ranked.md rows with planned at new (144 rows), first checked 2026-11-02.

| id | verdict | evidence | size |
|---|---|---|---|
| E18 | stale 2026-11-11 | `told_self` is now the neutral "the same note adds:" (ai/composer_digest.py:140); tests/test_composer_frames_1029.py:245-254 pins no "reminded yourself" / "You captured this" (v1028-1.md) | S |
| E24 | stale 2026-11-11 | `GENERATIVE_VERBS` and `GENERATIVE_THINGS` at ai/utilities.py:109-128, gate at routes_chat.py:205-222; tests/test_generative_asks_1102.py passes (44). One route case ("give me a study plan for next week") failed at head because g45-1110 F13 g (CHANGELOG.md:141) deliberately lays a study plan out from dated notes with no model; the test dropped that case (b9283286e, test only). (v1028-2.md) | S |
| E25 | stale 2026-11-11 | `commands.read('create a note called "Shopping" with milk, eggs and bread')` gives `Shopping\nMilk, eggs and bread`; pinned by tests/test_new_note_called_1102.py:18 (v1028-3.md) | S |
| E29 | stale 2026-11-11 | CHANGELOG.md:1060 (same reminder not made or listed twice); pinned by tests/test_reminder_dupes_1102.py (v1028-4.md) | S |
| D24 | fixed 483b6a6 | The document editor drop target (`docFileDropBox`) moved to documents-embeds.js; the shared paste and drop listeners stay in settings-wiring.js because chat, palette and notes use them too. | S |
| K16 | stale 2026-11-11 | SECURITY.md:115 says a space is not a security boundary; CHANGELOG 944; tests/test_audit1028_low_1102.py (v1028-1.md) | S |
| B28 | stale 2026-11-11 | frontend/js/whiteboard.js:18891 `wbPastedPictureAddress` (text/uri-list, img[src]), `wbPictureCap` 50 MB; pinned by tests/test_audit_1028_a28s.py::test_b28 (passes). (v1028-2.md) | S |
| E47 | stale 2026-11-11 | `#chat-sidebar-search` at index.html:2796 (search-field recipe, wired to `GET /conversations?q=`); pinned by tests/test_chat_ui_a28u.py:22. Find inside one chat (Ctrl+F) was never built; it was the optional half of the row, not the fix named (v1028-3.md) | S |
| E49 | stale 2026-11-11 | CHANGELOG.md:1070 (turn read from `data-turn`); pinned by tests/test_chat_ui_a28u.py (v1028-4.md) | S |
| E64 | stale 2026-11-11 | CHANGELOG 1059 acts name notes by title; tests/test_no_ids_in_act_text_1102.py (passes); the cited commands.py lines no longer hold `#id` (only `#tag`) (v1028-1.md) | S |
| E71 | stale 2026-11-11 | chat-turn.js:2537-2548 the Read aloud item turns to Stop reading while it speaks; speed is the Settings select `pref-read-aloud-rate` (index.html:13092, settings-controls.js:840, media.js:371 clamps 0.75 to 1.5); tests/test_chat_ui_a28u.py::test_e71 passes. (v1028-2.md) | S |
| B34 | stale 2026-11-11 | `#wb-empty-cue` keeps one line on an empty board (whiteboard.js:15711, 22342); tests/test_audit_1028_a28s.py:78 (v1028-3.md) | S |
| D53 | stale 2026-11-11 | CHANGELOG.md:1072 ("Output cut at 4,000 characters." marker); tests/test_audit_1028_a28s.py:93 (v1028-4.md) | S |
| E41 | stale 2026-11-11 | CHANGELOG 1065; frontend/js/ai-tools.js:114 hides Use this model for the one in-use model, :128 "loads when you ask"; activity-panel.js:35; tests/test_chat_ui_a28u.py (v1028-1.md) | S |
| E61 | stale 2026-11-11 | "Plan and Agent need a model." visible line plus aria-disabled Agent (a Tab stop) with the model-offer popover; tests/test_chat_ui_a28u.py::test_e61 passes. (v1028-2.md) | S |
| E67 | stale 2026-11-11 | composer_plan.py:515 builds Next chips from the answer's items; tests/test_due_chips_1102.py (v1028-3.md) | S |
| E68 | stale 2026-11-11 | CHANGELOG.md:1067 (`aria-busy` on the transcript while streaming); tests/test_chat_ui_a28u.py, tests/test_spinner_recipe.py:325 (v1028-4.md) | S |
| E69 | stale 2026-11-11 | Correction is underlined, click offers Keep / Put back / Edit (frontend/js/autocorrect.js:225-245), server says "I read that as" (ai/composer_ack.py:23); `data-autocorrect` staying on the boxes is the intended design (same verdict as ranked BC1) (v1028-1.md) | S |
| S62 | stale 2026-11-11 | app-palette.js editor-mode block carries a "Search notes for" row into `openFinder(typed, { kind: "note" })`; tests/test_audit_1028_a28s.py::test_s62 passes. (v1028-2.md) | S |
| S91 | stale 2026-11-11 | status.js:505-518 `pageTitle.view` sets `document.title` per view (router paints it); `<html lang="en">` is right, the UI is English only and no locale setting exists; tests/test_audit_1028_a28s.py:32 (v1028-3.md) | S |
| S92 | stale 2026-11-11 | CHANGELOG.md:1078 (count announced through the live region); tests/test_audit_1028_a28s.py:101 (v1028-4.md) | S |
| U38 | stale 2026-11-11 | frontend/js/documents.js:2701-2710 toasts once on a duplicate title and leaves it as typed; CHANGELOG 1077; tests/test_audit_1028_a28s.py (passes) (v1028-1.md) | S |
| U48 | stale 2026-11-11 | whiteboard.js `wbExportBoard` has `let scope = hasSelection ? "selection" : "whole";`; tests/test_audit_1028_a28s.py::test_u48 passes. (v1028-2.md) | S |
| B32 | stale 2026-11-11 | whiteboard-map.js has one rAF and one setTimeout, both inside `wbMapCache.defer` (:240-249) with cancel via `cancelAnimationFrame`/`clearTimeout`, and `wbMapCache.cancelAll()` runs on board switch; tests/test_audit_1028_a28s.py:54 (v1028-3.md) | S |
| K35 | stale 2026-11-11 | CHANGELOG.md:1071 (schema fingerprint in `PRAGMA user_version` skips the column scan); tests/test_schema_stamp_k35.py (v1028-4.md) | S |
| E58 | stale 2026-11-11 | Checkpoint rounds do not reload the list: `loadConversationList` runs on row create (chat-turn.js:421), retitle (:1168) and turn end (:1189) only; history is budgeted by `context.fit_history` (ai/agent_turn.py:142, E57) (v1028-1.md) | S |
| S90 | stale 2026-11-11 | notesPaletteCommands (app-palette.js:873) is still rebuilt per open, but the rebuild measured 0.02 ms of an 11.4 ms open (ranked.md row 276, shell.md S90 4 ms); a cache buys nothing and would go stale on note edits. (v1028-2.md) | S |
| B24 | stale 2026-11-11 | closed, won't do: 2 of 405 marker lines are bare; the citations are the trace to the owner's requests (dec-1111-w1.md) | S |
| K29 | stale 2026-11-11 | Lint `test_k29_an_async_route_touches_its_database_session_only_in_a_thread` (tests/test_audit1028_low_1102.py:110); the 7 remaining async routes (routes_auth.py:1537 lan_watch, routes_captions.py:113, routes_settings.py:2472, routes_tasks.py:644) offload DB reads or touch memory only (a30i-1102.md, backend-1111) (v1028-4.md) | S |
| B10 | stale 2026-11-11 | Export dialog states "Opens Print: choose Save as PDF" (whiteboard.js:14773); native PDF lib (jsPDF) declined in the vendoring review, HISTORY.md:214; the audit's own alternative ("document clearly in the export dialog") is met (v1028-1.md) | M |
| E57 | stale 2026-11-11 | d2e1629bb: turn reports `composition.history_dropped`, reply-kit.js:1593-1622 draws a `history-trimmed-notice` line under the reply; tests/test_history_trimmed_e57.py passes. (v1028-2.md) | M |
| E34 | stale 2026-11-11 | `liveMarkdownRenderer` (capture-ask.js:1207-1235) keeps finished blocks (`kept`/`keptCount`, `blockBreak` :1192) and draws only the open block, with adaptive gap `max(66, 4x render time)`; tests/test_live_markdown_blocks.py (v1028-3.md) | M |
| D25 | stale 2026-11-11 | closed, won't do: 20 to 160 later competing rules, 1.2 to 3.9 KB gzip gain (dec-1111-d1.md) | M |
| K11 | stale 2026-11-11 | Fixed b15530478: keyring else owner-only file, core/secrets_store.py, wired at core/config.py:405-416; tests/test_secret_settings_q22.py (passes) (v1028-1.md) | M |
| E43 | stale 2026-11-11 | 0389648d4: routes_chat.py:2454 `consent_store.refusal_for_press(body.consent_id, name, arguments)` binds the press to the parked card (tool name and arguments must match, card is spent); tests/test_confirm_binds_to_card_e43.py passes (3). A press with no `consent_id` is the Undo and redo path by design (consent_store.py:61). (v1028-2.md) | M |
| B33 | stale 2026-11-11 | `wbNum(v, fallback)` exists (whiteboard.js:9098), used for CSS lengths; tests/test_wb_board_1028.py:198. The remaining raw `parseFloat` calls are `\|\| 0` guarded or SVG path tokens; the isFinite guards are on parsed data, not style writes (v1028-3.md) | M |
| E59 | fixed 29a145e35 | "This answer is wrong" in the answer menu, POST /learned/answer-verdict (dec-1111-c1.md) | M |
| E60 | fixed 29a145e35 | Regenerate as another persona built; per-answer model closed as won't, not small (dec-1111-c1.md) | M |
| E62 | fixed 29a145e35 | Ask again widens the one shared search 5/10/15/20 (dec-1111-c1.md) | M |
| S71 | stale 2026-11-11 | file-drop.js (window-level `dragover`/`drop`, `fileDrop.note` matches .md/.markdown/.txt on the Notes tab, then `fileDrop.toNotes`) shows the drop veil and makes notes with Undo; tests/test_file_drop.py (v1028-3.md) | M |
| B26 | stale 2026-11-11 | The long board menu is flyout groups (Library, Arrange, Export) in `wbBuildContextMenu` (whiteboard.js:9506-9530, `buildMenuGroupButton`); pinned by tests/test_ux_1031_board.py (BD10). The function is still about 440 lines, but the scanning problem the row names is gone (v1028-4.md) | M |
| B23 | stale 2026-11-11 | Perf claim measured: export of 500 objects and 280 sketches builds in 17.9 ms in one task (CHANGELOG 183). The function is still 355 lines (whiteboard.js:13730), an arch item, not a freeze (v1028-1.md) | M |
| D45 | stale 2026-11-11 | closed, won't do: 30 to 47 ms once per load, a worker costs more (dec-1111-d1.md) | M |
| K34 | stale 2026-11-11 | routes_import.py:30-45 `_received` sizes the spooled upload by seeking (`app_import.size_of`), `app_import.expand` opens zips from the file and reads one member at a time (v1028-3.md) | M |
| E65 | stale 2026-11-11 | Declined with the measurement (s11-1110.md:10): `read_note` is not the cost, the per-answer queries were (329 to 96); a process cache adds invalidation risk for no measured gain (v1028-4.md) | M |
| D46 | stale 2026-11-11 | closed, won't do: 27.5% comments are the why text, already stripped at serve time (dec-1111-d1.md) | M |
| B3 | stale 2026-11-11 | Claim half true: whiteboard.js:22311-22316 `renderWhiteboard` still clears the size cache and `wbItemElCache`, but both are lazy lookup caches refilled on demand; the elements are kept (ranked.md row 14: 500 of 500 topic elements survive a render, 72.8 ms median at 4x throttle for one moved topic). tests/test_map_render_cost.py and tests/test_wb_stroke_paint_key.py pass (18). Not re-measured in a browser here. The comment at whiteboard.js:22313 ("replaces every map node's element") is out of date. (v1028-2.md) | L |
| B4 | fixed 578ea8b43 | paint keys already the dirty set; `classIfChanged` stops 1,060 no-op class writes per render (dec-1111-w1.md) | L |
| D26 | fixed (65c01c4, e3aae86) | Threads: author, time, replies, Show resolved and Reopen in the Comments rows (a30h-1102). | L |
| D30 | built | spelling packs fr, de, es as optional downloads, built d30-1111 (CHANGELOG 2026-11-11, tests/test_spell_packs_1111.py); the owner decided on downloads, not vendoring | L |
| E48 | fixed 29a145e35 | branch pager closed as won't (migration, reverses fork-copies); "Keep the earlier version as a copy" built (dec-1111-c1.md) | L |
| D22 | open | agent d2 building the library/boards split (dec-1111-d1.md has the design) | L |
| B15 | stale 2026-11-11 | closed, won't do: d3 v7 drag has no pointer-event option; the one-line bridge is pinned by tests/test_wb_edge_pan.py, reopen only if d3 is replaced (dec-1111-w1.md) | L |
| D23 | partial 483b6a6 | docCmTheme is documents-cm-theme.js; docLivePlugin (1,720 lines) still one function, line in DOCUMENTS_PLAN. | L |
| K24 | open | Re-checked 2026-11-11, still open: True: 9 Python files exceed 3,000 lines (composer_digest.py 6,230, engine.py 4,821, recognise.py 4,027, help_topics_more.py 3,915, routes_entries.py 3,777, help_topics_core.py 3,712, manager.py 3,595, database.py 3,345, __main__.py 3,013). Splits are L, and in progress in k24-1111.md (next: routes_entries connections block, routes_settings logs) (v1028-4.md) | L |
| K25 | open | Re-checked 2026-11-11, still open: Partly done (18 to 10 functions over 150 lines; `_start_tray`, `_build_graph`, `_optimization_pass`, `_run_skill`, `_dispatch_call`, `_prepare_turn`, `timeline` no longer over). Left: core/overlay/engine.py `__init__` 266, `_run_desktop` 245 (__main__.py:1898), routes_models.py `status` 201, app.py `_register_error_handlers` 194, entry/manager.py `_hard_delete` 181, wb_boards.py `list_boards` 181, facts.py `run` 173, routes_settings.py `_preferences_from` 167, app.py `_add_system_routes` 166, agent_turn.py `build_agent_messages` 160; L, one refactor per function (v1028-1.md) | L |
| E44 | open | Re-checked 2026-11-11, still open: True: chat-turn.js:11-1203 `chatSendTurn` is 1,193 lines. Over 150 lines and a risky refactor of the send path that needs a design (turn state, handler table, persistence, teardown) and a real-browser sweep per stage. (v1028-2.md) | L |
| E45 | open | Re-checked 2026-11-11, still open: still separate stream readers: answer-kit.js:1212 (`streamChatEvents`, shared by Ask/Chat), help-chat.js:543, agent-activity.js:568, chat-tasks.js:131. One `AnswerStream` plus one transcript component is a design (Opus rung), L (v1028-3.md) | L |
| D52 | fixed f98f2a9b0 | code-file tabs strip (dec-1111-d1.md) | L |
| D47 | fixed 875bceefc | fallback exercised by a sweep; the retry bug fixed (dec-1111-d1.md) | L |
| E19 | unsure | Needs the q1 run; lowercasing path in composer digest not located by grep. | S |
| E21 | unsure | Lowercase month tuples still at composer_doings.py:31 and composer_digest.py:2458; needs the q2 run. | S |
| E22 | unsure | _absent (composer_empty.py:68) checks length only; the caller stop list was not read. | S |
| E27 | unsure | CONFIRM_NOTICE (commands.py:1191) used on cards; whether done cards still show it needs a run. | S |
| U14 | unsure | Needs browser measurement of the dock gap between delete and undo. | S |
| U16 | unsure | Side tab size needs getBoundingClientRect at phone width. | S |
| U17 | unsure | Opaque grip ground added (07-whiteboard-misc.css:236-246); glyph contrast needs measuring. | S |
| U21 | unsure | Tools sheet labels need a phone render check. | S |
| U24 | unsure | Canvas edge margin needs a browser measurement. | S |
| U26 | unsure | Template strip clip needs a measurement at 1440. | S |
| U28 | unsure | Font size stepper units need a browser check. | S |
| U25 | unsure | Chevron overlap needs a screenshot measurement. | S |
| U30 | unsure | Toolbar heights need getBoundingClientRect. | S |
| B29 | unsure | whiteboard-format.js inline formatting needs a browser check on topics. | S |
| E55 | unsure | Untag without a tag name needs the q3 run. | S |
| D39 | unsure | Autocorrect defaults off (documents.js:15000); status bar switch not found; needs a UI check. | S |
| E37 | unsure | ai-status control at index.html:9181; red or neutral colour needs a browser check. | S |
| E52 | unsure | Coaching tip template at composer_aware.py:160; whether it sits outside the answer needs a run. | S |
| E53 | unsure | Last-time line at composer_voice.py:144; exclusion of app-made notes unconfirmed. | S |
| E63 | unsure | composer_body.py:619 avoids Also-joined sentences; the list rule needs a run. | S |
| E72 | unsure | why.py:65 still says Searched your notes; the nothing-matched line needs a run. | S |
| S55 | unsure | Label case needs a sweep of Settings strings. | S |
| S56 | unsure | toast-box CSS at 01-forms-settings.css:3001; bottom nav clearance needs a phone check. | S |
| S58 | unsure | Return focus needs a keyboard run. | S |
| S61 | unsure | Dark theme chip contrast needs a measurement. | S |
| S83 | unsure | Active filter chips not found by grep; needs a browser run. | S |
| S86 | unsure | Card open action needs a browser run. | S |
| S87 | unsure | Dashboard deep links need a browser run. | S |
| S88 | unsure | No search term highlight found by grep; needs a browser run. | S |
| S89 | unsure | No export format picker found by grep; needs a UI check. | S |
| S94 | unsure | Offline help text needs a read of status.js and a run. | S |
| U41 | unsure | Toast persistence needs a timed browser run. | S |
| U46 | unsure | Hidden board select is intentional; aria handling needs a check. | S |
| B38 | unsure | Move-many endpoint exists; the nudge caller was not traced. | S |
| S64 | unsure | 1031 S3 made avatars lazy; mascot gating not found by grep. | S |
| S67 | unsure | reply-kit.js:220 uses plural(); other duplicate helpers not traced. | S |
| S79 | unsure | Icon stroke weights need a visual check. | S |
| S80 | unsure | Card shadow tokens need a visual check. | S |
| S93 | unsure | flashEntry tests exist (test_blindux_1031.py); not-in-DOM path not confirmed. | S |
| U39 | unsure | Check mark overlap needs a screenshot. | S |
| U40 | unsure | Thumbnail placeholder needs a visual check. | S |
| U44 | unsure | Computed font size of find labels needs getComputedStyle. | S |
| E14 | unsure | Needs chain run (chain.py c1.json); 1029 C44 fixed it and that, so only pin and ordinal cases remain to check. | M |
| E16 | unsure | compare moved to composer_versus.py; needs the q2 run to see two identical lists. | M |
| E20 | unsure | Needs the q1 run to see weekday words listed as due; cue logic in composer_plan.py not read in full. | M |
| E33 | unsure | OFFLINE_LEAD unchanged (help_chat.py:836); whether the lead gives the path needs the h1 run. | M |
| B12 | unsure | Tab guards on boards and maps at whiteboard.js:66 and 3140; a per-mode shortcut table was not found. | M |
| D33 | fixed (b092d42) | The find panel has All documents and Replace in all, carrying its query and options (a30h-1102). | M |
| E23 | unsure | No cloze builder found by grep in ai/*.py; needs the quiz run. | M |
| E38 | unsure | No-model Models page needs a browser run. | M |
| E50 | unsure | Phone banner and card sizes need the pw9 measurement. | M |
| U15 | unsure | Needs browser measurement of the arrange menu height at 768 and 900 px. | M |
| U22 | unsure | Header height and title clip need a phone measurement. | M |
| U23 | unsure | Map pan after add needs a browser run. | M |
| U27 | unsure | Layout menu design needs a browser look. | M |
| U18 | unsure | Long tasks need a performance trace. | M |
| U19 | unsure | Long tasks need a performance trace. | M |
| U20 | unsure | Long task needs a performance trace of doc open. | M |
| D44 | unsure | Page-break class in documents-export.js:142; page preview not found; needs a check. | M |
| E56 | unsure | composer_help.py:27 treats pomodoro as a tool request; timer and calendar phrases need a parse run. | M |
| S74 | unsure | Outline exists for documents (app-features.js:86); none found for notes. | M |
| S76 | unsure | Hover card for note links not found by grep; graph hover card only. | M |
| D48 | unsure | 17 doc-dock-menu references; reparenting not traced. | M |
| S68 | unsure | Import panel density needs a visual check. | M |
| S69 | unsure | Restore summary not found by grep; backup UI needs a read. | M |
| S85 | unsure | Toast action buttons need a read of status.js. | M |
| U49 | unsure | Tab stop count needs a keyboard run. | M |
| K36 | unsure | list_boards in wb_boards.py:41 not traced for per-board queries. | M |
| S65 | unsure | Precache list size needs a read of sw.js. | M |
| B39 | unsure | Module singletons remain (whiteboard.js:21169 area); reset on board switch not traced. | M |
| S66 | unsure | tests/test_frontend_symbols.py exists; its scope for lazy modules not read. | M |
| D18 | unsure | Live view rebuild needs profiling; doc.toString copies found only in documents-code.js. | L |
| D42 | unsure | CSV runs as a table (documents-code.js:2885) but no editable grid was found. | L |
| U12 | fixed | index.html:6929 and 6931 add R and A key hints to Rectangle and Arrow. | S |
| D35 | fixed | HISTORY line 51850: a failed fetch toasts with Try again (tests/test_open_document_failure_d35.py). | S |
| D38 | fixed | HISTORY line 51849: the run-job heartbeat checks a generation (jobSeq). | S |
| S82 | fixed | index.html:2452-2466 view toggle carries title and aria-label. | S |
| S84 | fixed | app-features.js:203 Welcome tour replay entry (reveal onboarding). | S |
| S57 | fixed | HISTORY line 19: New note button overlap found already built, measured at 390 and 1440. | S |
| S63 | fixed | app-palette.js:39 and 71: note results with snippets from search kind=note. | M |
| B30 | fixed | app.js:1627 LAZY_MODULES lists whiteboard-library, templates and interchange. | M |
| B37 | fixed | routes_whiteboard.py is now 64 lines; wb_board, wb_items, wb_map and others split out. | M |
| S81 | fixed | settings-find.js:21 describes sticky pane heads with the current one marked. | M |
| S77 | fixed | obj-reorder.js:227 Custom order is on line; drag and Alt+arrow reorder. | L |
