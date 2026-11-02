# Batch E (audit 1029 rows 1, 2, 15, 29, 32, 33): remaining

Done: rows 1 (partly), 2, 15, 29, 32, 33; see `git log` on the worktree branch.

- Row 1 X5, undo bin for "Delete everything in it": not done. The delete-with-contents path still removes rows and unlinks files for good (`delete_space`, src/tessellate/api/routes_spaces.py, the long block after "Deleting a space deletes what was in it"). A bin needs the contents kept (soft delete, or a restore manifest with the files held back) for the standard window; that conflicts with the owner decision at WHITEBOARD_PLAN.md:529 ("none by design: confirmed, its files leave the disk") unless the owner reopens it. What landed: the dialog selects "Move everything to Default space" first and counts "N notes, M documents" (`GET /spaces/{id}/counts`) in its line and in the destructive option.
- Row 2 X2: the guard is `recordingLive()` beside `chatMidStream()` in frontend/js/navigation.js and runs on beforeunload only, not in `hasUnsavedWork`, because a tab switch leaves the recording running in its dock (a "Leave without saving?" there would be wrong). Say if the owner wants it on tab switches too.
- Row 2 X3: a zero-size row left "recording" on the server after a crash is finished or purged by `recordings.recover_stale` on the next start (unchanged); the dialog no longer claims "Saved as it goes" at size 0.
- Not verified: a real microphone (the sweep used Chromium's fake device); the browser's own leave-page prompt (a native dialog the sweep cannot read).
- Found, not fixed: `tests/test_global_scope_ratchet.py` fails on the base commit (702 top-level let/var, cap 699), not from this batch. `deleteCategory` in frontend/js/categories-panel.js:831 has no caller (its stand-in entry was removed from app.js to win bytes).
- Row 29: with more than twelve spaces `listFilter` puts a text field inside the menu; axe was run with ten spaces only.
