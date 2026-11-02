# composer5-1031 remaining list

done: items 1 to 5 of the brief, tested over many phrasings in `tests/test_composer_five_1031.py` (fixed clock, Friday 30 October 2026).
- 8dfc983 compare names every side (2 to 6) and strips format tails (`composer_sides.py`, `composer.compare_sides`).
- Next commit: show/latest/dates (items 3 to 5): `filed_name.shows_the_lot`, `note_recency.status_subject`, `composer_digest._lead_day`/`_said_day`, `composer_lists._until`; CHAT_PLAN decision 81.

Left (found, not fixed):
- "what's new with uni" is not read as a latest ask by the composer (left to the retrieval default; `status_subject` needs a latest, newest or recent word).
- The digest's `_REGISTER` context var is set by `_set_timing`; tests wrap calls in `contextvars.copy_context().run` so it does not leak. A caller that sets it outside a request would leak it the same way.
- CHAT_PLAN.md is at 1891 lines against the 1900 cap; the next decision there needs a move to HISTORY first.
- Older tests changed with a comment citing decision 81 or the date table: `test_composer_lists_1018.py` (`_until` forms, "home notes" show versus list), `test_gold_answers.py` (gym line), `test_composer_labels_1018.py`, `test_composer_grammar.py`.
- Not run here: the full suite (by order); real-model checks.
