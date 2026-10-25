# composer6-1026 (CHAT_PLAN 1353)

Done: composition layer (`ai/composer_compose.py`, `composer_lines.py`); abilities migrated: recent notes, due, plan, left, definitions, counts, countdown/since, study heads; welcome (`chat_extra.welcome_line`, hello in chat); needle control (`ai/needle_control.py`).
Latency (200 seeds x 7 abilities): p50 0.05 ms, p95 0.15 ms (limit 5 ms, tested).
Next: reach (item 5): reminder notification text, dashboard today-line/empty states, toasts; persona to voice in Settings route; migrate social kinds (thanks, how, bye) and quiz feedback; "nothing found" in composer.py (pieces trace).
