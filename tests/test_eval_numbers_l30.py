"""L30: the composer and voice eval figures, recorded as floors so a regression shows (measured 2026-11-12,
no model, fixed showcase notebook; no earlier figures were kept, so these are the first record).

Composer (25 questions, `python -m tests._composer_eval`): grounded 1.0, redundancy mean 0.095 and max 0.333,
7.5 words a sentence, 4.0 connectives an answer, 18 distinct openers, 0 repeated lead-ins, 25 first-line answers,
context 15 percent smaller prompt. Twenty turns in one chat: 16 distinct openers, 13 alone.
Voice (`python -m tests._voice_eval`): companion 20 of 20 distinct with 4 openings and 20.3 words; today 7 of 7;
week 7 of 7 (87.7 words); find 25 of 25 distinct with 25 openings; searches 3; titles 75; every surface grounded 1.0.
"""

from __future__ import annotations

from tests import _composer_eval, _voice_eval


def test_composer_eval_figures_hold():
    rows = _composer_eval.run()
    now = _composer_eval.summary(rows)
    assert now["questions"] == 25 and now["grounded"] == 1.0
    assert now["redundancy_mean"] <= 0.12 and now["redundancy_max"] <= 0.34
    assert now["first_line_answers"] == 25 and now["lead_in_repeats"] == 0 and now["says_colon"] == 0
    assert now["openers_distinct"] >= 18 and now["connectives_distinct"] >= 45
    chat = _composer_eval.session_summary(_composer_eval.session())
    assert chat["session_openers_distinct"] >= 16 and chat["session_lead_in_repeats"] == 0 and chat["session_grounded"]


def test_voice_eval_figures_hold():
    table = _voice_eval.run()
    assert {k: v["count"] for k, v in table.items()} == {"companion": 20, "today": 7, "week": 7, "find": 25, "searches": 3, "titles": 75}
    assert all(row["grounded"] == 1.0 for row in table.values())
    assert table["companion"]["distinct"] == 20 and table["companion"]["openings"] >= 4
    assert table["find"]["distinct"] == 25 and table["find"]["openings"] >= 25
