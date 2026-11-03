Counts: fixed 13, open 59, unsure 72. Source: audit-1028-ranked.md rows with planned at new (144 rows), checked 2026-11-02.

| id | verdict | evidence | size |
|---|---|---|---|
| E18 | open | composer_digest.py:130 and 3005 still add the told_self phrase to note sentences. | S |
| E24 | open | composer_write.py:55-58 covers translate and rewrite only; essay and timetable asks get no needs-a-model reply. | S |
| E25 | open | commands.py:515 _new_note keeps the quoted title as body text; no split on with. | S |
| E29 | open | No duplicate reminder check in act_registry.py or commands.py. | S |
| D24 | open | Paste and drop file upload still in settings-wiring.js:1922, with fileDropBox at 1957. | S |
| K16 | open | Space isolation is still an ORM filter on a client header (core/deps.py:378); no not-a-boundary note. | S |
| B28 | open | No text/uri-list handling in the whiteboard.js paste path. | S |
| E47 | open | index.html has no chat list search box; no find-in-chat control found. | S |
| E49 | open | chat-edit.js has no data-turn attribute; the cut still derives the turn from bubble index. | S |
| E64 | open | commands.py:1356 and 1400 still put #id in card items. | S |
| E71 | open | No speed control; the Read aloud menu item has one label (chat-turn.js:2507). | S |
| B34 | open | Dismiss hides the hint (whiteboard.js:15426-15427); no replacement inline cue found. | S |
| D53 | open | No truncated marker in documents-code.js run output. | S |
| E41 | open | index.html:10127 still shows Use this model with one model; activity-panel.js:34 says not in memory. | S |
| E61 | open | index.html:3296 explains the disabled Plan control only in its data-needs-model title. | S |
| E67 | open | composer_plan.py:412 offers a single Plan my week chip. | S |
| E68 | open | chat.js:387 sets aria-busy only on web-panel; no transcript busy state found. | S |
| E69 | open | No as-typed echo found; data-autocorrect still on quick note and title inputs (index.html:1221, 1680). | S |
| S62 | open | app-palette.js empty state has no Search notes for fallback. | S |
| S91 | open | status.js:509 sets document.title only for the unread count, not per view. | S |
| S92 | open | No aria-live region in notes-list.js or library.js. | S |
| U38 | open | No duplicate-title warning or suffix found in document create. | S |
| U48 | open | whiteboard.js:14637 defaults the export scope to On screen when nothing is selected. | S |
| B32 | open | whiteboard-map.js has 2 requestAnimationFrame calls and no cancelAnimationFrame. | S |
| K35 | open | database.py:2919 and 2964 run PRAGMA table_info per table each start; no schema_version gate. | S |
| E58 | open | chat-attach.js:1344-1365 reloads the whole conversation list on each refresh; no patch found. | S |
| S90 | open | notesPaletteCommands is rebuilt on each open (app-palette.js:846); no cache. | S |
| B24 | open | Decision and INBOX markers remain in whiteboard.js and whiteboard-map.js comments. | S |
| K29 | open | Async routes remain: routes_auth.py:1473 lan_watch and routes_tasks.py:644 jobs_stream. | S |
| B10 | open | whiteboard.js:14439 export still opens the browser Print path; no native PDF. | M |
| E57 | open | No inline notice where turns drop; only compress suggestions (chat-turn.js:696, chat.js:1124). | M |
| E34 | open | ask-compose.js liveMarkdownRenderer still re-renders the whole answer per flush (capture-ask.js:1263). | M |
| D25 | open | Document styles still spread across 17 css files (grep doc-). | M |
| K11 | open | llm_api_key still stored in preferences; the keyring seam covers only the PIN store (pinstore.py). | M |
| E43 | open | routes_chat.py:2436 /tools/execute has no signature tying the call to a parked card. | M |
| B33 | open | 23 raw isFinite or isNaN checks in whiteboard.js and no shared number helper. | M |
| E59 | open | No thumbs or helpful control in chat js files; only insight Confirm and Not right. | M |
| E60 | open | No Regenerate with or Continue after Stop item in chat-turn.js. | M |
| E62 | open | chat.js:187 sends attempt to reword; no widened retrieval on regenerate found. | M |
| S71 | open | No drop target for files on the notes list (notes-list.js, library.js). | M |
| B26 | open | wbBuildContextMenu is still 448 lines (whiteboard.js:9251). | M |
| B23 | open | wbBuildExportSvg is still 339 lines and reads live DOM styles (whiteboard.js:13502). | M |
| D45 | open | documents.js:16206 builds the dictionary on the main thread; the worker only runs grammar. | M |
| K34 | open | routes_import.py:30-41 still reads uploads into bytes, no spool to disk. | M |
| E65 | open | composer_read.py:440 read_note has no NoteView cache; functools.cache only wraps a regex. | M |
| D46 | open | documents*.js comment lines are 10,103 of 36,378 (28 percent). | M |
| B3 | open | whiteboard.js:21916 renderWhiteboard still clears the map size cache and item element cache each render. | L |
| B4 | open | wbScheduleRender (whiteboard.js:21762) has no dirty set; renderWhiteboard runs the full board per frame. | L |
| D26 | fixed (65c01c4, e3aae86) | Threads: author, time, replies, Show resolved and Reopen in the Comments rows (a30h-1102). | L |
| D30 | open | Spellcheck still uses one en.txt wordlist (vendor/wordlist, ASCII, lowercased); no other dictionary is vendored, so a per-document language needs new lists first (a30h-1102.md). | L |
| E48 | open | chat-edit.js has no branch or pager; edit still truncates later turns. | L |
| D22 | open | documents.js is still 857,982 bytes and unminified; CodeMirror now loads lazily (documents.js:16443). | L |
| B15 | open | whiteboard.js:17922 still dispatches a synthetic MouseEvent mousemove bridge. | L |
| D23 | open | docLivePlugin still in documents-cm.js:28 and docCmTheme at 1608; split by file only. | L |
| K24 | open | Nine Python files still exceed 3,000 lines, e.g. composer_digest.py 5,203 and routes_entries.py 4,373. | L |
| K25 | open | _start_tray is 351 lines and _run_desktop 325 (__main__.py:2162, 1780); 10 functions over 150 lines. | L |
| E44 | open | chat-turn.js:11 chatSendTurn still runs 1,171 lines. | L |
| E45 | open | Five consumers remain: answer-kit.js:1053 streamChatEvents, ask-compose.js askController, help-chat.js, agent-activity.js. | L |
| D52 | open | No code editor tabs found in documents-ide.js. | L |
| D47 | open | Textarea fallback still present (documents.js:226). | L |
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
