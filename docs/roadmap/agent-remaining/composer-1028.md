# Composer audit 1028 (agent/composer-1028): remaining

Done (commits on agent/composer-1028, tests in `tests/test_composer_1028.py`, `tests/test_guide_aliases.py`):

- E6, E30, E7, E12: e1c2fc9 (a day a note says counts as in the window, "when was X written" is its own date answer, a missing embedding package is "off" not "loading", bare titles name notes for tag/rename/pin/delete, unfinished acts say how to finish).
- E11: 97d5455 (lists due for a subject, kind or window, still-to-do over several checklists, summary of every note on a subject).
- E31: b1c3118 (`ai/guide_aliases.py`: hard rows outrank keywords, soft rows only follow them; "Did you mean" on a miss).

Remaining:

- E10 (tasks as acts): not started. It needs an act in `act_registry.ACTS` over the reminders machinery; one brief row, not built here.
- E31: the alias table has about 50 rows against the brief's 60; the soft rows add phrasings, the hard rows (18) fix measured misses. "Did you mean" fires only when nothing matched, not on a weak keyword match.
- E32 and E33 (ChatGPT synonyms, lead with the path) are untouched.
