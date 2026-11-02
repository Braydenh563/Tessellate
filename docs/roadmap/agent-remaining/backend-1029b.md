# backend-1029b

Done:
- row 9: request caps (persona, mode, skill inputs, tool bodies, file text and save bodies, lint); the earlier caps (history, media, pins, graph id) were already in commit 9024ece
- row 10: blank notes and reminders, comma tags, space names (invisible, spacing, reserved), snooze step date error
- row 51: Statistics `left_out` line, health DB size with WAL and shm
- row 61: one `withoutEndStop` for the embedding notice detail
- row 63: service worker cache `tessellate-assets-`, both legacy prefixes deleted on activate

Remaining:
- A request-body bound lint for every route file: 120 str, list and dict fields in `src/tessellate/api/*.py` bodies have no `max_length` (routes_whiteboard.py 26, routes_conversations.py 17, routes_settings.py 12, routes_entries.py 11, routes_models.py 9); the lint in `tests/test_input_bounds_1029.py` covers routes_chat, routes_files and routes_graph only.
- `SpaceCreate.name` and `SpaceUpdate.name` have no `max_length` at the model (the 60-character check is in `routes_spaces._validate_name`, a 400 after the body is read); `EntryCreate.category` and `EntryUpdate.category` are unbounded (src/tessellate/api/schemas.py).
- The Reminders form in the page (frontend/js/wiring.js:1583) still relies on the server to refuse "31 February"; no client-side message was added.
