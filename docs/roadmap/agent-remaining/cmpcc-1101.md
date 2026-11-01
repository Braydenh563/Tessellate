# cmpcc-1101: four composer functions under the complexity limit

Order: week_review (composer_voice.py:588), _others (composer_body.py:182), _opening (composer_body.py:38), _score (composer_select.py:150).
Per function: a characterisation test pinning its exact output (golden in tests/fixtures/composer/), committed; then the split, the seed row removed.
_score is hot (per candidate): timeit over 2,000 candidates before and after.

- done: week_review characterisation (tests/test_week_review_paths.py, 15 cases, 45 of 45 lines)
- next: week_review split, composer_voice.py:588
- done: week_review 32 to under 15 (composer_voice.py `_review_span`, `_review_filed`, `_standouts`, `_review_standouts`, `_review_open`); not hot
- next: _others and _opening characterisation (tests/test_composer_body_paths.py, written, golden not yet), composer_body.py:38 and :182
- note: tests/test_composer*.py is about 10,000 tests, two hours at -n 2 under this load: run once at the end on the final head; per step the golden tests, voice, complexity and line caps
