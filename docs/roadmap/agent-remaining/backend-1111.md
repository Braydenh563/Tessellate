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
- K32: design is `GET /reminders/due` (count, next due, stamp) with status.js reusing its list on an unchanged stamp; ETag/304 rejected (API is no-store). Not built: routes_reminders.py and status.js are the reminder-Complete worker's.
- K19: closed; a session open across `reload_db` keeps reading, jobs are waited for first (CHANGELOG 1293).
- K29: closed; the six async routes offload or touch only memory.
- E9: unverifiable here (no Tesseract, no PDFium).

## Hand-offs
- Settings row for `mcp_writes_enabled` (index.html control, SETTING_ROWS entry, settings-panes.js and settings-controls.js load/save, help line, GET key with the NO_ROW lint reconciled). Until then MCP writes cannot be turned on from the UI.
- MCP writes do not mark the search index stale (`deps.mark_index_stale` would write preferences.json from the MCP process and be overwritten).
- Base failure, not mine: tests/test_graph_furniture_1029b.py help panel 1131 > 1000 chars.

## Remaining
- BK10: `/library` and `/graph` payloads carry full content per row; needs a shape decision with the frontend (ledger: stale in part, FIT42 waits on Q9).
- W2 (next).
