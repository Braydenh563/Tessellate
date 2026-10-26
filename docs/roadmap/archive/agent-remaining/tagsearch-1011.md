# tagsearch-1011 (Sonnet), rows 1271 to 1353

id | status | evidence or commit

1271 | built | clear/restore reach discarded_tags (routes_inbox.py), counted in GET /suggestions/dismissed, Settings line + Undo carry note_tags; tests/test_suggestions_inbox_kg9.py::test_tags_turned_down_on_notes_are_counted_cleared_and_restored
1272 | left | whiteboard: a free line stores its path as the endpoints, so trimming the shaft at a hollow end would drift the line; needs the untrimmed endpoints stored beside the path (whiteboard.js wbShaftEnd/WB_HOLLOW_INSET). Not started: whiteboard owner
1273 | closed-measured | tagging.py: tags from a note's own words for a notebook with no tags scored 4 of 12 (filing-1010.md), rejected on that number; nothing to build
1274 | done-already | measured at 1440: .doc-backlink-action border 0, background transparent, 28px tall (05-sidebars-themes.css:5978, quiet row action); the tool-confirm pair belongs to the agent/Ask owner
1275 | not-verifiable | link-label blur needs a GPU compositor or the desktop webview; not reproduced headless (whiteboard)
1276 | left | Documents sidebar Comments, Linked from, Notes rows (index.html:4616-4640, .doc-outline-wrap); visual consistency, Documents owner (DOCUMENTS_PLAN); not measured
1277 | skipped | undo (another agent owns undo)
1278 | built | #dash-quicklinks scrollWidth 1412 to 1408 and scrollHeight 101 to 97 at 1440; 1024 999=999; 600 584=584 (08-consistency.css, ring room only under 600); at 390 the 4px is the scrolling strip's ring room, held by tests/test_ring_room.py
1279 | left | whiteboard More sheet at 390 is 59 to 62 rows; a filter field is a whiteboard-menu design call (whiteboard owner)
1280 | built | notebook_stats._notebook_block counts links and orphans only between counted notes; tests/test_notebook_stats_page.py::test_a_link_to_a_binned_or_private_note_is_not_a_link_on_the_page
1281 | done-already | closed in HISTORY.md, "OPEN.md rows closed, 2026-10-05 (the open-ledger pass)"
1282 | left | maptheme: needs a schema and export design (theme carried, not resolved per node) and a real FreeMind file for <arrowlink>; MINDMAP owner
1283 | left | #wb-search-toggle and #wb-navigator-toggle duplicate the View menu by design (UI_MODERNISATION Phase 8 names them as the bar's find zone); the open part is a #wb-context-menu sweep, whiteboard agent
1284 | done-already | navigation.js hasUnsavedWork (1692) no longer counts the capture box; tests/test_unsaved_work_guard.py
1285 | done-already | GET /most-opened + EntryOpen log + dashboard "most-opened" widget (routes_vision.py:112, dashboard.js:68), tests/test_vision_rows_row11.py::test_most_opened_counts_this_month_only; its "wrong" correction half is the Ask evidence card (skipped, Ask owner)
1286 | skipped | Ask: the "wrong" correction on an evidence card
1287 | not-verifiable | needs a real 384-dimensional backend; this machine has no sentence-transformers (standing caveat, CLAUDE.md section 4)
1288 | built | embedmodels.snapshot_state/is_downloaded now need weights AND config.json; a partial folder is downloaded as a visible task ("Downloading the search model", embeddings._fetch_model_as_a_task); tests/test_embedding_offline.py
1289 | built | a model that will not load is fetched again as a visible task "Fixing search by meaning" (jobruns kind embedding-fix), up to REPAIR_ATTEMPTS=2, keyword search meanwhile, "Reinstall" only after the second failure; no class names in the first message; tests/test_embedding_offline.py::test_the_fix_is_a_visible_task_and_the_person_is_asked_only_after_two_failed_fixes
1290 | built | each built-in row says Downloaded, <size on disk> / Not downloaded / Files missing + Reinstall (embed-choices.js, catalogue state and on_disk); size counts weights kept in the shared blob store (was 1015 KB for a 127 MB model); measured 1440 and 390: no overflow, 44px targets at 390
1291 | closed-informational | settings.js:159 fills the Models-pane checkboxes when Background tasks or Web search opens; the note records where the code is, not a defect
1292 | built | autonomous.NO_MODEL_DETAIL: a pass whose agent answered offline says "Skipped: no model is running"; tests/test_autonomous.py; _optimization_pass complexity 42 to 41 (seed lowered)
1293 | done-already | ux1005-palette.js (removed 2026-10-12, recoverable from git history), search1005-lazy.js and readmeshots.js read command rows only (palette is commands and places, INBOX 666)
1294 | built | embeddings backfill honours Stop between batches (passes.STOPPABLE, jobruns.stop_asked); Settings, Packages keeps one line pointing to Search and index in place of its second embedding list; tests/test_embedding_backfill.py::test_stop_ends_the_backfill_between_batches_and_keeps_what_was_embedded
1295 | built | GET /entries/{id}/related leaves out notes already linked and a draft against a committed note; tests/test_related_notes.py::test_related_leaves_out_a_note_that_is_already_linked
1296 | closed-decision | notes keep the updated_at rule on purpose (the board-only guard stays); lexical_filing keys on updated_at; nothing to change
1297 | built-partly | as before; INBOX 1297 asks the owner to keep, trim or drop memorymap_everyday.json (recommendation keep)
1298 | built | WORLD_CLASS_PLAN decision 6 corrected: MemoryMap's own list of 49 (memorymap_filing.json), the pack has no flag
1299 | built | WORLD_CLASS_PLAN decision 56 corrected: the taxonomy stays under src/memorymap/ai/data/taxonomy/
1300 | built | WORLD_CLASS_PLAN decision 4 amended to what is built (pack labels via entry/tidy.py _rows_category_names); the person's own titles dropped, a title is not a name for its category
1301 | closed-by-design | with the search model off the merge review uses topics alone at 0.8 and says so in the row (tidy.MERGE_TOPIC_OVERLAP_ALONE)
1302 | closed-decision | the tag picker on an empty field is a completion list by use, not a suggestion; left as the row says
1303 | not-verifiable | what a real small model answers to the tag prompt; the grounding (tests/test_tag_grounding.py) holds whatever it says
1304 | left | Documents (Brief 42 remainder: highlights, comments with bookmarks, link cards, long-form preference, local graph, doctype.js under 30 ms); DOCUMENTS_PLAN owner
1305 | closed-record | counts of a 13 to 23 note sweep; a measurement caveat, no work
1306 | closed-record | the Notes sidebar has no search field; the routes built are the no-match Search everything button and the saved-search rows
1307 | left | import cost 3.3 s against 1.5 s: autonomous imports ai.agent (503 ms), help_chat 271 ms, routes_search 226 ms; not measurable at load average 40 to 55 (a bare import app took 18 s wall, 4 s user); lazy-import ai.agent in autonomous when the machine is quiet
1308 | partly | focus ring in Chat not reproduced: 59 stops, 0 under 2px or 3:1, min 3.56:1 light and 7.03:1 dark (focusring.js TABS=chat); only #chat-input has none (the composer, skipped). touch.js Settings: with a 4 s wait (was 900 ms, the first open loads settings-controls.js) general 19, models 8, appearance 31, preferences 7, account 18 controls measure 0 under 44px, 0 covered, 0 overlapping; data and privacy still read 0 controls though both are visible (display block, 4642px and 1760px), which is the sweep's checkVisibility(contentVisibilityAuto), not the app: sweep left. overlap.js: #dash-quicklinks gone at 1440 (1278); #notes-tidy 4px is the Tidy count badge on the broom's corner by design (08-consistency.css:783); .library-controls and #tab-notes .layout 4px at 390 are ring room; found and fixed the dashboard digest notice (1343)
1309 | left | graph neighbours follow a drag by 20 to 50 of 340 units; a per-drag local anchor is conditional on the owner still finding dragging stiff (graph100-1011.md)
1310 | done-already | tests/test_properties_never_in_previews.py::test_the_dashboards_note_widgets_read_past_the_block passes on this head
1311 | done-already | tests/test_ownerfix_1011.py::test_a_link_row_underlines_its_words_not_its_icon passes on this head
1312 | built | janitor.ModelStalled: after one miss the model is not asked again for FILING_STALL_COOLDOWN_SECONDS=60 (notes filed by meaning at once), a late answer ends it; tests/test_background_filing.py (3 tests). Not measured against the 20-note burst on a stand-in server
1313 | built | janitor._model_slots: at most FILING_MODEL_CONCURRENCY=4 inline notes wait on the model, the rest are filed by meaning, so 20 simultaneous POST /entries cannot fill the pool (5+10); tests/test_background_filing.py::test_only_a_few_inline_notes_wait_on_the_model_at_once. Not measured against the real pool
1314 | skipped | phone: pinch handles (phone2 owner)
1315 | done-already | tests/test_settings_row_heads.py lints every .setting-label head
1316 | not-verifiable | close in meaning against a real embedding model (no torch/sentence-transformers here)
1317 | partly | tests/test_inbox_435.py and tests/test_companion_motion.py pass on this head; tests/test_undo_contract.py skipped (undo owner)
1318 | done-already | BACKLOG section 3 status: Browse is the web panel (36G), Chat/Agent is the mode toggle; the one gap is an Agent-mode allowed-tools control, Agent owner
1319 | left | treemap/sunburst: GRAPH_PLAN VC11 (D3 hierarchy layouts) is the row; graph owner, needs its decision first
1320 | left | subway map: needs an edge-routing pass in graph-canvas.js, "do last" (graph owner)
1321 | left | sea chart: a skin over a layout plus a parchment token pair; graph owner, DESIGN.md recipe first
1322 | skipped | Chat/Ask token cost (re-sent notes every turn); Ask owner
1323 | done-already | TOOLS_GUIDE says a result is a clipped sentence and read_url exists (ai/agent.py:415, BACKLOG "Done since")
1324 | left | query expansion for web search: needs a live engine to judge the gain; a second request per search is a cost with no measurement behind it
1325 | needs-decision | a global quick-capture hotkey needs a new Python dependency (pywebview has none): the owner's call (FIX_COMMON rule 2)
1326 | needs-decision | multi-category notes (entries.category_id to a join table): BACKLOG 23 says decide with the owner whether tags already serve it; touches the single-valued assumption of filing, sidebar counts and the graph
1327 | needs-decision | manual collections (a table and a join table): same owner question as 1326
1328 | done-already | no #wb-search element in index.html; removed in 993e639
1329 | needs-decision | email-in is a second outbound connection (IMAP poll) against "web search is the one feature that goes online": the owner's call
1330 | built | POST /entries/suggest-category (words only, no model, no write) and a "File under <category>" chip beside the suggested tags in Capture, shown while Filing is on Atlas's choice; tests/test_suggest_category_draft.py; measured 1440: chip 24px like the tags, reason on hover, click sets Filing; decision: same row as the tags, no new switch
1331 | done-already | POST /entries/link-suggestions/reasons and the Suggest reasons button (BACKLOG, Built)
1332 | built | GET /search hits carry category (routes_search._with_categories: the note's category, null for other kinds; tests/test_search_hit_category.py), and Find anything's Sort has Group by category (a note under its category with a count, the rest under their kind; search.js finderRender); the row's claim that the route already returned it was false
1333 | closed-decision | BACKLOG records the lever was the count (capped at 6) because a single local model serialises; revisit only for a batching server
1334 | closed-decision | ai_first_filing is a preference; with the stall guard (1312) a slow model costs one wait a minute, not one per note
1335 | closed-record | the owner's context for the research scope, not a request
1336 | done-already | start.sh:1132, start.bat:670, README.md:319, docs/INSTALL.md:137, onboarding.js:86 say the first setup needs the internet once
1337 | skipped | composer: a one-line answer above search results
1338 | done-already | undo toast and the "Not suggested" list with restore chips (tag-suggest.js, note-edit-panels.js:501); this session adds the count and a clear in Settings, Data (1271)
1339 | skipped | Chat: sources dropdown order (Ask/Chat owner)
1340 | done-already | Brief 39b steps 1 to 5 built (WORLD_CLASS_PLAN 23 Steps); the open part is decision 8 (1297)
1341 | skipped | phone: Notes capture as a full-height sheet with swipe actions (phone owner)
1342 | done-already | tests/test_settings_ia.py::test_a_link_names_the_section_that_holds_its_target
1343 | done-already | no-model notice 46.8px (one row) at 1440 and 1024, 93.6px at 390, sentence 74 chars; found by overlap.js and fixed: in the dashboard digest card (306px) the words were a 52px column nine lines tall (157px notice), now the action sits under them as on a phone, 261px of words, 82px (#dash-grid .ai-offline-note rules in 03-dashboard-widgets.css, boot CSS 178435 of 183300 gz; the recipe stays no-wrap); Chat and Writing room notices unchanged at 47px
1344 | done-already | EntryProperty and the properties block (GRAPH_PLAN KG4)
1345 | partly | topbar 44px at 1440 and 1024 (57.8px at 390, the phone bar); axe (light, 1440) on the dashboard: 1 serious finding on 3 controls (label-content-name-mismatch: status counts, a finished first step) fixed to 0 (tests/test_label_in_name_1345.py); notes and settings surfaces not scanned (the browser was killed twice by memory pressure); Brief 41 owns the rest
1346 | partly | T1 and T2 built (tidy.js: back link, empty review with no bar, Recent runs disclosure); T3 (undo a confirmed pattern) is undo-owned, T4 (menu end gaps) is grammar57-owned
1347 | not-reproduced | measured at 1024 and 1100: all 16 Writing room and Capture rows are one line (m5, boxes stacked vertically); wrap only at 390
1348 | done-already | filed_by_label names the signal (words, meaning with the embedding model); tests/test_filing_accuracy.py records no model 0.417 and the embedder 0.808; no sentence-transformers means embed_text returns None and filing is the words path that table measures
1349 | done-already | composite names ("Fitness & Health") in lexical_filing.py (decision 2, line 353 and 686)
1350 | skipped | composer spec tests (spec39)
1351 | skipped | composer spec tests (spec39)
1352 | skipped | composer spec tests (spec39)
1353 | done-already | every tag path grounds the model's tags in the note's own words (routes_entries._engine_tags, three callers; tests/test_tag_grounding.py); with no model tests/test_filing_accuracy.py::test_tags_offered_are_only_the_notebooks_own; a real model not run

1307a | deferred-next-PR | lazy-import of ai.agent in autonomous needs a quiet machine to measure the saving (load 40 to 55 here)
WIP verified: group-by-category in Find anything (`tests/test_search_hit_category.py`), CHANGELOG and help present; INBOX 1297 placed for the owner.
1332 | measured | Chromium 1440: Find anything "garden" with Sort = Group by category lists headings "Work 3" then "Journal 3" with the notes under each
