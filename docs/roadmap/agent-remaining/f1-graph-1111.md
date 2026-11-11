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

Built in run 2 (2026-11-11), HISTORY "F1 run 2": gap row 6 (the ```base block, a read-only table of notes by property), gap row 5 (synced blocks: a `![[Doc#^id]]` window edits its source, DOCUMENTS_PLAN 26 decision 82) and gap row 10 (Edit here on a board card opens the board in a dialog; whiteboard.js gained `openWhiteboardBoard(id, { stay: true })` and a cancelable `wb-leave` event, no per-instance refactor).

Checks done in run 2 (:8796): dark Live graph at 360, 820 and 1440; bookmarks-import Undo in the UI; bookmarks file round trip; HTML export of a graph and a base block (found and fixed: no plot styles in the file, key swatch lost with the style attributes, a base block saved as "Reading the notes", row names removed with the buttons).

Left, true:
- Video embed: out by decision 2 (audio is a recording; no video attachment).
- Not verified: print preview of a plot (the `@media print` rules in the lazy CSS cover it, not driven); Escape and the dialog's minimise and resize inside the board dialog; the Library loses its open board while the dialog is open and is left on the board list.
