# backend-1111 (spoke claude/pr216-backend, W5, W6, W32)

Verified on head c334542, 2026-11-11. No code change was needed: every W5, W6 and W32 row is built, stale or held on an owner call.

## Done / stale (verified)
- W5 A22 to A30: fixed or stale earlier (struck in OPEN.md). K33 fixed 8d9cfce9e (`_token_valid` sweeps at most every 30 s). K38 part-fixed 8d9cfce9e (access log prints `once=...`).
- W6 A32 to A36: struck w6-1110 (tests/test_recording_is_unsaved_work_1029.py, test_xfix_1031.py, test_wb_board_1028.py).
- W32: E7 built c6cc5767a. K27 done s14-1110 (4 dead routes removed; the rest keep test callers). K20 stale (unreachable, export_folder.py:693-699). K22 built (`core/clock.py`, test_drifted_copies_1031). K37 built (`PRAGMA optimize` at quit, core/database.py:3329). BK4 built (client log rate limit, routes_settings.py:2357). BK6 built (`update_verify`, detached signature in routes_update.py:147). K36: `list_boards` is paged with grouped counts; only the preview field is one query per page row (wb_boards.py:41-90), 200 rows at most.

## Held (owner call, not mine to decide)
- Q22: K11 key storage (keyring or 0600 file), K13 MCP auth, K26 two schema systems, E43 `/chat/tools/execute` card binding (OPEN.md A31, H4).
- K38: single-use media links break range playback; accept a 120 s reusable link? (H4)
- K32 / BK12: `/reminders/due` count endpoint changes the poll (H4).

## Remaining, not started
- BK10: `/library` and `/graph` payloads carry full content per row (235 KB, 289 KB at 530 notes); needs a shape decision with the frontend.
- K19 / BK5: `reload_db` disposes the engine with requests in flight (core/deps.py:236); needs a reproduction first.
- K29: six route files mix `async def`; not measured.
- E9: real Tesseract and PDFium reads never ran (needs the binaries).
