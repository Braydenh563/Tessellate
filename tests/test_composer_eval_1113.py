"""The floors for the five composer eval sets CHAT_PLAN section 4 named (L-chat-22): time windows,
recall, social turns, out-of-domain questions and how-to questions. Each set is a fixture in
`fixtures/composer/` written by `scripts/composer_fixtures_1113.py` (every expected value worked
out from the row itself, never by running the engine), read by a `run_*` and a `*_summary` in
`tests/_composer_eval.py`. A set the engine misses a floor on is a LEDGER row, and its test asserts
the measured number as a ratchet that only goes up."""

from __future__ import annotations

from tests import _composer_eval


def test_every_time_phrase_reads_to_its_exact_window():
    got = _composer_eval.windows_summary(_composer_eval.run_windows())
    assert got["rows"] == 60
    #: Includes the forms measured as missed ("since March", "the week before last", "on 3 March" read
    #: as past) and the regression that "last friday" is the past Friday.
    assert got["exact"] == 1.0, got["missed"]
    phrases = {r["phrase"] for r in _composer_eval.run_windows()}
    assert {"since March", "the week before last", "on 3 March", "last friday"} <= phrases


def test_recall_questions_name_the_right_notes_in_order_and_count_them():
    rows = _composer_eval.run_recall()
    got = _composer_eval.recall_summary(rows)
    assert got["rows"] == 30
    kinds = {k: sum(r["kind"] == k for r in rows) for k in dict.fromkeys(r["kind"] for r in rows)}
    assert kinds == {"time": 8, "person": 4, "place": 3, "changed": 5, "due": 4, "open": 3, "contradicts": 3}, kinds
    assert got["ids_in_order"] >= 0.9, got["missed"]
    assert got["count_rederived"] == 1.0, got["missed"]
    assert got["empty_window_says_so"] == 1.0, got["missed"]


def test_social_turns_read_as_their_kind_and_replies_stay_alive_and_true():
    rows = _composer_eval.run_social()
    got = _composer_eval.social_summary(rows)
    assert got["rows"] == 80
    counts = {g: sum(r["group"] == g for r in rows) for g in ("kind", "humour", "identity", "control", "gratitude")}
    assert counts == {"kind": 48, "humour": 8, "identity": 6, "control": 12, "gratitude": 6}, counts
    assert len({r["kind"] for r in rows if r["group"] == "kind"}) == 15
    assert got["kind_accuracy"] >= 0.95, got["missed"]
    assert got["regenerations_differ"] == 1.0
    assert got["replies_invent_nothing"] is True
    assert got["identity_names_atlas"] is True


def test_out_of_domain_questions_are_answered_plainly_and_never_invented():
    got = _composer_eval.ood_summary(_composer_eval.run_ood())
    assert got["rows"] == 30
    assert got["grounded"] == 1.0
    #: Ratchets, not floors: the plan's floor is 1.0 on each. The misses are LEDGER row L-chat-40
    #: (plan step 11): 3 questions show a note with no no-answer, 29 say nothing of what the app can do,
    #: 10 show a note without calling it the closest. Raise these as that row lands.
    assert got["plain_no_answer"] >= 0.9, got["missed"]
    assert got["capability_line"] >= 0.033
    assert got["closest_labelled"] >= 0.667


def test_how_to_questions_open_on_the_first_step_and_name_real_controls():
    got = _composer_eval.help_summary(_composer_eval.run_help())
    assert got["rows"] == 40
    assert got["controls_exist"] == 1.0
    #: The plan's 0.90 floor (L-chat-41): the answer opens on the topic's first-step sentence, the place after it.
    assert got["first_sentence"] >= 0.90, got["missed"]
