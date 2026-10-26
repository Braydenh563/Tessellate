# composer6-1026 (CHAT_PLAN 1353)

Done: composition layer (`ai/composer_compose.py`, `composer_lines.py`); abilities on it: recent notes, due, plan, left, definitions, counts, countdown/since, study heads, the next-step closing (`composer_tone.closing`); welcome (`chat_extra.welcome_line`: hello in chat, empty dashboard line); persona cue to voice (`routes_chat._chat_voice`); needle control (`ai/needle_control.py`); act-done line for command cards.
Latency (200 seeds x 7 abilities): p50 0.05 ms, p95 0.15 ms (limit 5 ms, tested).
Remaining:
- (social how/sorry/laugh/reaction/confused/ack/compliment done, composer7: composer_lines SOCIAL_HEADS/TAILS, the stored lists stay as fallback for other kinds and for tests) composer.py nothing-found / empty_window / insult / emotion / who kinds are still stored lists (composer.py:3296 SOCIAL, :4236 empty_window); they carry grounding pieces, so move them with their trace tests.
- (quiz feedback and summarise_done done, composer7: commands.summarise_done(say), routes_chat._act_planned_events)
- reminder notification text is built in the browser (frontend/js), not reachable without growing the boot gzip cap; needs a lazy file.
- tests/test_plan_hygiene fails on CHAT_PLAN.md 1905 > 1900 since the base (placement of 1353): move a Built block to HISTORY.
