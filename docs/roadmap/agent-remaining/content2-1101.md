# content2-1101: row 2a steps (2) the undo table and (3) the export walker

Branch agent/content2-1101 from claude/sharp-thompson-45hngp at 2d1e774; port 8855.

Decided here (row 2a left them open):
- The undo table holds every kind with a bin mark: note, board, document, file (its way back is its note's), reminder, recording. A binned OCR reading is not a row with a bin mark but a former value of a file's text (`core/reading_bin.py`); putting it back rewrites the file's reading, region cache and index after the commit, so it keeps `/reading-bin/{id}/restore` and `binRoutes` keeps one branch for it.
- The old per-kind restore routes stay (tests, and the undo stacks in documents.js, shell-reminders.js and meetings.js call them) and go through `content.restore`; the Library bin reads `POST /bin/{kind}/{id}/restore`.
- A thumbnail PUT is a write: a binned board answers 409 by `BOARDS.writable`; its state and image reads keep 404.
- The walk reads what the session reads: binned notes are walked (the exports keep `_recycle-bin`), binned documents stay under the bin floor as the folder export always had them (byte-identical proof). Records stay in `entry/export_folder.py` by kind, not on the adapter: a note's record needs the bulk `_related` loader built once per export.

- done: 10b1218 step (2) the undo table, the thumbnail 409, the recording purge DELETE; drive on :8855 (untracked `content2/drive-bin.js` in the session scratch).
- done: step (3) the export walker; proof: `content2/export_hash.py` in the session scratch, seed once, hash a copy before and after: 28 hashes, digest 07b37d40 both.
- next: none in row 2a. Open, owner's call: a binned document is left out of the folder export while a binned note goes in (src/tessellate/repo/content.py `walk`, entry/export_folder.py `_write_documents`); recommend walking binned documents too (the import already restores `deleted_at`), with `_existing_documents` reading the bin so a re-import merges them.
- Not built: the recordings and reminders write routes still 404 a binned row (their own `_get`/`_existing`), not the guard's 409; `KINDS` now has their adapters, so it is one call each.
