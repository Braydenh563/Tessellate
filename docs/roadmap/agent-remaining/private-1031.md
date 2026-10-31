# private-1031: BACKLOG 1481, a private chat in Chat

Branch `agent/private-1031`, port 8798, data `$S/data-private`.

- done: bcd31de server half (`ChatRequest.private`; tests/test_private_chat.py).
- done: page half (chat-private.js lazy, chat-private-lazy.css, hooks in chat-attach.js, chat.js, sheets-selects.js, capture-ask.js, wiring.js, reveal-targets.js, settings-panes.js, index.html), DESIGN row and lint, Guide topic `chat-private`, manual parity row, CHANGELOG (both), BACKLOG 1481 moved to HISTORY.

Left, one line each:
- A skill run's own tool list is not filtered for `save_user_preference` (routes_chat.py, the `run_skill` branch of `_run_agent_events`; skill_runner.py has no `blocked_tools`).
- The web panel's recent searches (chat.js `WEB_SEARCH_HISTORY_KEY`, localStorage) keep a typed web query in a private chat.
- The chat head's ⋯ row is labelled "Private chat" in both states (kebabMenu rows have no checked state); the head's mark and the settings switch's `aria-pressed` show the state.
- `tests/test_plan_hygiene.py::test_inbox_is_a_tray_not_a_backlog` fails at 20 INBOX items on the base too (1483, 1484 added by the owner); not touched here.
