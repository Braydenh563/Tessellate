# composer7-1026 (CHAT_PLAN 1353 / 1351)

Done (tests/test_composer_seven_1026.py, test_composer_compose_1026.py):
- composer5: no unticked tasks in a definition's Also line (`composer_digest._drop_tasks`); "what's my next exam" and "exam date" read the reminder (`composer_plan._WHEN_IS_NEXT`).
- composer6: quiz feedback composed (`quiz_*` frames); small talk how/sorry/laugh/reaction/confused/ack/compliment built from SOCIAL_HEADS x SOCIAL_TAILS in the chat's voice and mood (16+ lines a voice, `composer.social_surfaces`); command card "Done" line composed (`commands.summarise_done(say)`).
- dog2: items 1, 2, 3, 4, 10, 23 ticked (built earlier, tests exist); an empty weekday or span window says so and names the next date (`due_none`), a bare "the next 7 days" is a due question.
Latency: test_composing_is_cheap green (limit 5 ms). Complexity: test_complexity fails only on needle_provider.chat_tools and routes_board_library.paste_board_items, both on the base, not mine.

Left:
- dog2 19 "Sources: ... meaning + keywords" on every answer: say the mode only when it changes (chat-agent.js:2232, `lastHow` on chatSourcesPanel); +60 bytes breaks the boot gzip cap (320600), needs the lazy bundle.
- Reminder notification text is built in the browser (frontend/js), same cap.
- composer.py stored SOCIAL kinds still stored: insult, emotion, who, about_app, joke, unclear, test, and the nothing-found PHRASES (composer.py:4290 `_nothing`); `empty_window` is already lead + span from two pools. The stored lists for the composed kinds stay as the tests' reference (test_reply_variety, test_composer_tables read them); delete with those tests' sample sets.
- Empty-window "Next up" line is not yet in the professional voice's own words (plain `Next up:`).
- Not verified: small talk through the running app with a real persona prompt (unit and route tests only); no model.
- Carried: compare N-way and as a table, quiz on a whole category, the grounding "Heads up" against a real model (composer5).
