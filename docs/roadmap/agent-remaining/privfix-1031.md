# privfix-1031: private chat keeps nothing (BACKLOG 1481)

Done: the one switch `core/private_turn.py` (`scope`, `stepped`, `route`), read by `events.record` (turn bookkeeping rows), `memory.persona_with_memory`, `agent.run_agent` (blocks `save_user_preference`), the `save_user_preference` tool, `StreamNarrator`, `_remember_rows`, `_log_question`, `_verdicts`, `_insight_memory`, `_run_title`. The `private` parameters on `_prepare`, `_log_question`, `_resolve_persona`, `_verdicts`, `_insight_memory`, `persona_with_memory`, `run_agent`, `_prepare_turn` are gone. Tests: `tests/test_private_chat_tools.py`.

Left, one line each:
- A raw thread started inside a turn does not inherit the flag (`tools/__init__.py` `prefetch_web`, `ThreadPoolExecutor`): it only fills the web caches and logged nothing carrying the query in the test; if a worker there ever logs or writes, start it with `contextvars.copy_context().run`.
- `routes_websearch.py:86,295` write `web_searched` / `web_read` rows (entity `chat`) from the page's own buttons, outside any private scope: the page does not call them from a private chat today; check `frontend/js/chat-attach.js` if that changes.
- `JobRun.say` (`core/jobruns.py:319`) is not itself gated: only the narrator builds turn lines. A new caller that says a question's words from inside a turn must read `private_turn.active()`.
