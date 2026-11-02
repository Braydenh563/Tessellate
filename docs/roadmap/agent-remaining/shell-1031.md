# shell-1031 remaining list

done: one commit for S11, S15, S21, S22, S38, S40, S43, S44, S72 (b8cfb46).
Already built, measured in the running app: S28, S29, S31, S32, S33, S50, S70, S73, S75.

Left:
- S53 (timeline and notes list page separately): not started. Needs a decision on one shared page-size and cursor between `frontend/js/timeline.js` (chunked append near line 725) and `frontend/js/notes-list.js` (windowed rows near line 1940).
- S36 (import preview): not built. DESIGN.md line 713 makes import one step with Undo plus a report (`routes_import.py` has no dry run); a preview is a recipe change, so it is a decision for the owner (INBOX entry with this recommendation: keep one step).
- S3, S16, S42: skipped as large. S16: the notes list is already windowed, so the row's premise is stale and needs re-measuring before any work. S3: the mascot code left the boot (bootlazy-1031.md); index.html comment stripping is the open half. S42: sample notes on first run.
- Search: negated operators (`-tag:`, `-cat:`) are not supported in `src/tessellate/search/query.py`; S50 is built without them.

Caveats:
- S15 was measured in Chromium forced-colors emulation, not on Windows High Contrast. Theme cards use `.theme-swatch` (inline background), not `.theme-preview`.
- S72 was not run on an empty data dir (needs a fresh server); the hint text is covered by a test only.
- S43 palette detection is covered by a test and a regex; not driven live.
- Budget: boot scripts sit within 1 to 2 hundred bytes of TOTAL_CAP in `tests/test_static_compression.py`; the reminder edit form moved to `reminder-edit.js` to make room.
