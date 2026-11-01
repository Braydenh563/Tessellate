# content2-1101: row 2a steps (2) the undo table and (3) the export walker

Branch agent/content2-1101 from claude/sharp-thompson-45hngp at 2d1e774; port 8855.

Decided here (row 2a left them open):
- The undo table holds every kind with a bin mark: note, board, document, file (its way back is its note's), reminder, recording. A binned OCR reading is not a row with a bin mark but a former value of a file's text (`core/reading_bin.py`); putting it back rewrites the file's reading, region cache and index after the commit, so it keeps `/reading-bin/{id}/restore` and `binRoutes` keeps one branch for it.
- The old per-kind restore routes stay (tests, and the undo stacks in documents.js, shell-reminders.js and meetings.js call them) and go through `content.restore`; the Library bin reads `POST /bin/{kind}/{id}/restore`.
- A thumbnail PUT is a write: a binned board answers 409 by `BOARDS.writable`; its state and image reads keep 404.
- The walk reads what the session reads: binned notes are walked (the exports keep `_recycle-bin`), binned documents stay under the bin floor as the folder export always had them (byte-identical proof). Records stay in `entry/export_folder.py` by kind, not on the adapter: a note's record needs the bulk `_related` loader built once per export.

- done: step (2) commit below; drive on :8855 (untracked `content2/drive-bin.js` in the session scratch).
