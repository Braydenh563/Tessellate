# fable-fix-1030 (agent fable-fix, branch agent/fable-fix-1030)

Done: c5a24ea (F2, F3, F6, F7, F8, F9, F10, F13, F14, F15; Z64, Z69, Z71). F1, F4, F5, F11, F12 were fixed before this run (1ffd38b, 34612fa).
Fixed on the base before this run, not reproduced here: Z67 (the Sara, Tokyo trip and Books notebook answers from the Sara notes only).

Found, not fixed:
- F13 (closed 68e396e: `questions._title` went to the shared reader): `composer._title`, `composer_lists._title` and `questions._title` stay (allowlisted in the lint): `questions._title` is pinned by `tests/test_quadratic_scans.py` as a byte-equal scan, so it moves with that pin, not here.
- F14 (closed: `bounds.squeeze_blanks`, checked a30e 1102): the chat request has no whitespace-run cap; the regexes are linear on their own.
- F15: fixed 2026-11-02 for the note's checklist (both readers), "what is still open" and any pool holding an open box (`composer_slots.done_later`). The named-note ask ("what is in my admin bits note") closed 68e396e and 88fd715.
- **Open (checked 2026-11-09).** F6: the model path is tested through the fake transport only; real inference is unverified (CLAUDE.md section 4).
- **Open (checked 2026-11-09).** F8: measured on a loaded machine with a 600-note synthetic notebook: `composer_digest.answer` 5.2 s to 3.8 s first call, 2.0 s to 1.4 s repeat; rerun on a quiet machine before quoting.
- **Open (checked 2026-11-09).** Pre-existing red at the branch base (not from this run): `test_composer_owner_1017::test_a_hello_ends_on_an_ask_about_the_newest_note`, `test_composer_owner_1030::test_a_choice_the_app_offered_opens_that_note`, `test_composer_study_1025::test_more_and_shorter_after_a_summary`.
- **Open (checked 2026-11-09).** Z59 (the streak line is pinned by `tests/test_composer_streak_1029.py`), Z57, Z58, Z68, Z70, Z46 recast, and the older Z rows listed in `composer-z-1030.md`.

Next: Z57, Z58, Z70 (drop the Uncategorised label and unmatched notes from the model context), Z68 (a model-up Ask run), then Z23, Z26, Z27.
