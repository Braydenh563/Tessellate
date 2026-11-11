# F1 graph block run (agent F1, 2026-11-11)

Done: the graph block (HISTORY, "F1 graph block"); Guide topic `document-graph`. Checked stale: VC4, VC7, VC6 own words, VC13 fold-all (evidence in OPEN F1); click on a rendered equation opens the editor (built).

Left, one line each:
- Ctrl+K "Insert equation" row: built (app-features.js; tests/test_equation_palette_row.py; driven over a note box and in a document on :8796).
- VC13 lint panel: stale, the Problems tab of the bottom panel (Ctrl+Shift+M, documents-code.js:3535) already lists every finding.
- VC17 Emmet scss, sass, stylus: satisfied by the scss/sass to css alias.
- Gap rows 1 (video and audio embed: blocked by the audio-is-a-recording decision; embed a recording by name, documents-embeds.js), 5 and 6 (L, design step first), 9 (clipper fields on note properties, M; documents-props.js, web-clip.js), 10 (canvas block, M; board embed editable in place, documents-embeds.js); L6 browser bookmarks HTML import and export (`api/routes_bookmarks.py`, library.js Bookmarks tab).
- Graph block not verified: real touch gestures, print and HTML export of a plot (not checked what they show), dark Live at widths other than 1440.
- L6 browser bookmarks HTML import and export: built (repo/bookmarks_html.py, routes_bookmarks.py, library.js `renderBookmarks.file`; tests/test_bookmarks_html.py; driven on :8796 at 1440 and 390: 3 added, second import all twins, export downloads, menu rows 44 px, no overflow). Tags on bookmarks: built (tags column, add and edit field, #tag chips, search, TAGS attribute; tests/test_bookmark_tags.py; driven at 1440 and 390).
- Gap row 9 (clipper fields on a note's properties): built (core/webclip.py, routes_webclip.py; tests in test_webclip*.py).
- Gap row 1 recording embed: built (`![[a recording's name]]` in Edit and Read; tests/test_doc_recording_embed.py). Not supported: Notes-tab `![[recording]]` when the Library bundle is not loaded.

Blockers (true, with the first step):
- Gap row 10 (board embed editable in place): whiteboard.js holds one global `wbState` and `#whiteboard-container`. Step 1 (whiteboard.js, off limits to this run): make the state per instance; step 2: mount it from documents-embeds.js `docEmbedNode`'s `board` branch. Size L.
- Gap row 5 (synced blocks): `![[Doc#^id]]` is read-only (`docEmbedNode` block branch). An editable transclusion needs a design (where the text lives, how a save in either place reaches the other). Size L.
- Gap row 6 (database view): no cross-note property query endpoint exists (only `repo/properties.py` per entry and `types()`). Step 1: a `GET` that lists notes by property; step 2: a lazy table-only `base` block renderer; board and calendar views after. Size L.
- Video embed: out by decision 2 (audio is a recording; no video attachment).
