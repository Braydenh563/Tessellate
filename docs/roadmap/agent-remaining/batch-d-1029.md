# Batch D, audit 1029 (rows 25, 12, 11, 9): remaining

Done: rows 25 (H3, H4, H5, H6), 12 (H9), 11 (X11), 9 (H10, X26, N18, G27). Left, one line each:

- Stream routes other than chat (`/help/ask/stream`, `/drafts/*` streams, `/insights/digest/stream`, document streams, routes_help.py:80, routes_drafts.py:113, routes_insights.py:717, routes_documents.py:1203) have no deadline and no disconnect watcher: `core/deadline.py` covers non-stream routes only. A first-byte limit for a stream needs its own entry kind in `DEADLINES`.
- `core/deadline.py` `DEADLINES` lists seven POST routes and two decorating GETs; the other model-calling POST routes (night, suggest, link reasons, map suggest, translate, ocr reads) are not in the table yet. Measure each under the `chathang` fake and add a row; do not add a number in a route.
- chat.js:1062 and settings-controls.js:1189 still call `/websearch/searxng/status` when web search is off (the route now answers in under 300 ms from the last answer, 503 while it has none). Skipping the call needs the menu to stay reachable for DuckDuckGo users (B55).
- One lint over request models (`max_length` on every list and name field) is not written: `tests/test_input_bounds_1029.py` covers the five named inputs only. Candidates: a test that walks `app.openapi()` schemas for arrays and strings without a bound, with an allowlist that can only shrink.
- Media upload sniffing refuses empty files and markup named like an image; magic-byte checks per type were not added because many fixtures upload placeholder bytes under an image name.
- `/models/hardware` first call after a start still pays up to two short budgets (about 0.5 s) before the answer is known; the second call is under 300 ms. `prewarm_installed` covers the list, not the loaded names.
- Not verified against a real Ollama or a real Docker: every check ran against a local socket server that accepts and never answers, and a shimmed `docker_available`.
