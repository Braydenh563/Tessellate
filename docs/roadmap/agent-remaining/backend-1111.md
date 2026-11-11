# backend-1111 (spoke claude/pr216-backend, W5, W6, W32)

Verified on head c334542, 2026-11-11. No code change was needed: every W5, W6 and W32 row is built, stale or held on an owner call.

## Done / stale (verified)
- W5 A22 to A30: fixed or stale earlier (struck in OPEN.md). K33 fixed 8d9cfce9e (`_token_valid` sweeps at most every 30 s). K38 part-fixed 8d9cfce9e (access log prints `once=...`).
- W6 A32 to A36: struck w6-1110 (tests/test_recording_is_unsaved_work_1029.py, test_xfix_1031.py, test_wb_board_1028.py).
- W32: E7 built c6cc5767a. K27 done s14-1110 (4 dead routes removed; the rest keep test callers). K20 stale (unreachable, export_folder.py:693-699). K22 built (`core/clock.py`, test_drifted_copies_1031). K37 built (`PRAGMA optimize` at quit, core/database.py:3329). BK4 built (client log rate limit, routes_settings.py:2357). BK6 built (`update_verify`, detached signature in routes_update.py:147). K36: `list_boards` is paged with grouped counts; only the preview field is one query per page row (wb_boards.py:41-90), 200 rows at most.

## Built (batch 2, Q22 answered)
- K11 b155304 `core/secrets_store.py`: OS keyring, else 0600 file; old plaintext key migrates out. Also fixed the codeql 228 cap at its cause (test_state_machines_1747).
- K13 6ff76a7: one token per notebook (`TESSELLATE_MCP_TOKEN`, in the Settings snippet), MCP read-only until `mcp_writes_enabled`.
- E43 0389648: `/chat/tools/execute` press is bound to its card (409 for a spent, unknown or different-action card).

## Decided (standing order 3)
- K26: closed by design (additive columns vs alembic, three tests hold the line).
- K38: keep the 120 s reusable link (bound to path and session token, log-scrubbed); single use breaks Range playback.
- K32: BUILT 62af9c7 (see Batch 3 below). Design was `GET /reminders/due` (count, next due, stamp) with status.js reusing its list on an unchanged stamp; ETag/304 rejected (API is no-store). Not built: routes_reminders.py and status.js are the reminder-Complete worker's.
- K19: closed; a session open across `reload_db` keeps reading, jobs are waited for first (CHANGELOG 1293).
- K29: closed; the six async routes offload or touch only memory.
- E9: unverifiable here (no Tesseract, no PDFium).

## Batch 3 (hub's third message)
- Settings row for `mcp_writes_enabled` b009105: checkbox "Let that app add and change notes" in Tools it can use, GET key, SETTING_ROWS entry, load, save, Guide line, round-trip test.
- Graph help panel b009105: copy cut to 1000 characters (test cap kept).
- K32 62af9c7: `GET /reminders/due` (open, next_due_at, stamp) and `openReminderList` in status.js; the list is fetched only when the stamp moves. Not driven in a browser; covered by tests/test_reminders_due_stamp_k32.py and node-free source checks. The note title shown in a toast can stay stale until the next change to the list.
- BK10: closed, nothing to add. `/library` rows are clipped (`_clip`), the map asks `/graph?slim=1`, and the note list asks `/entries?preview=300`; the one full read left (`notes-lazy.js:36`, `ids=...&boards=include`) hydrates whole notes on purpose.
- W1: re-verified (46 targeted, 425 `test_chat_*` pass); no Playwright run this session.
- W11: re-verified (326 `test_notes_*` and `test_search_*` pass); every row was already stale or built.
- Base reds, not mine: `tests/test_global_scope_ratchet.py` 9046 names against a cap of 9044 (also red on origin/claude/next-queue-1102); `tests/test_reminder_notifier.py::test_a_reminder_fires_once_with_no_window_and_done_from_it_marks_it_done` (fails on the base too, a real-clock test).

## Hand-offs
- MCP writes do not mark the search index stale (`deps.mark_index_stale` would write preferences.json from the MCP process and be overwritten).

## Remaining
- Nothing open in this batch.
