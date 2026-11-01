# cmpcc-1101: four composer functions under the complexity limit

Order: week_review (composer_voice.py:588), _others (composer_body.py:182), _opening (composer_body.py:38), _score (composer_select.py:150).
Per function: a characterisation test pinning its exact output (golden in tests/fixtures/composer/), committed; then the split, the seed row removed.
_score is hot (per candidate): timeit over 2,000 candidates before and after.

- done: week_review characterisation (tests/test_week_review_paths.py, 15 cases, 45 of 45 lines)
- next: week_review split, composer_voice.py:588
- done: week_review 32 to under 15 (composer_voice.py `_review_span`, `_review_filed`, `_standouts`, `_review_standouts`, `_review_open`); not hot
- next: _others and _opening characterisation (tests/test_composer_body_paths.py, written, golden not yet), composer_body.py:38 and :182
- note: tests/test_composer*.py is about 10,000 tests, two hours at -n 2 under this load: run once at the end on the final head; per step the golden tests, voice, complexity and line caps
- done: _opening, _others and _score characterisation (tests/test_composer_body_paths.py 1,327 cases, tests/test_select_score_paths.py 242 cases; every line of the three)
- next: _opening and _others split (new code parked in scratchpad cmpcc/body_new.py), composer_body.py:38 and :182
- done: _opening 28 and _others 30 to under 15 (composer_body.py `_opener_options`, `_fresh_openers`, `_OPENERS_BY_SHAPE`; `_other`, `_joiners`, `_by_note` also in `_timeline` and `_earlier`); not hot
- next: _score split (new code in scratchpad cmpcc/select_new.py, bench cmpcc/bench_score.py), composer_select.py:150
- done: _score 28 to under 15 (composer_select.py `_Scorer`); cpu ms per call, 2,000 candidates (10,028 sentences), 4 question shapes, scores equal, median of 30 interleaved: before 136.9, after 104.7
- next: tests/test_composer*.py once on the final head, then the report
