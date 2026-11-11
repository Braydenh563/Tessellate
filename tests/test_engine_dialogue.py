"""Variation and the conversation (CHAT_PLAN Phase 6 step 4, decisions 34
and 35): a 20-turn session over the showcase, Ask again, the dialogue state
carried in the request's history, and the route's retry."""

from __future__ import annotations

import functools
from datetime import datetime, time

from tessellate.ai import composer
from tessellate.ai import recognise_questions
from tessellate.core import deps
from tessellate.core.config import user_now
from tessellate.entry import manager
from tests import _composer_eval
from tests.test_composer_route_688 import _ask


def test_a_twenty_turn_conversation_opens_more_ways_and_repeats_no_joiner():
    alone = _composer_eval.session_summary(_composer_eval.session(dialogue=False))
    talk = _composer_eval.session_summary(_composer_eval.session())
    assert talk["session_grounded"] and alone["session_grounded"]
    assert talk["session_lead_in_repeats"] == 0
    assert talk["session_openers_distinct"] >= 15
    assert talk["session_openers_distinct"] > alone["session_openers_distinct"]


def test_three_regenerations_differ_and_keep_the_lead():
    answers = _composer_eval.regenerations()
    texts = [a["text"] for a in answers]
    assert len(set(texts)) == 3
    assert len({(a["grounding"][0]["note_id"], a["grounding"][0]["start"]) for a in answers}) == 1


def test_outside_a_conversation_the_same_question_gets_the_same_words():
    data = _composer_eval.load()
    entry = data["questions"][0]
    notes = _composer_eval.notes_for(entry, data)
    on = _composer_eval.today(data)
    first = composer.compose(entry["question"], notes, today=on)["text"]
    assert composer.compose(entry["question"], notes, today=on)["text"] == first


def test_the_dialogue_is_read_from_the_history():
    history = [{"question": "When is the dentist?", "answer": "On 27 September you wrote: Check-up booked for the 21st."}]
    talk = composer.Dialogue.from_history(history)
    assert talk.turns == 1 and talk.salt == composer.Dialogue.from_history(history).salt
    assert composer.PHRASES["wrote_on_b"] in talk.used
    assert "dentist" in talk.topic_stack


def _seed(session, on_day=None) -> None:
    for content in (
        "# Gym log\n\nI went to the gym on Monday and did squats. I like the morning sessions best.",
        "# Running\n\nI ran 5 km on Saturday in 28 minutes. The new shoes helped on the hills.",
        "# Gym plan\n\nI plan to go three times a week. Decided to go with the strength programme.",
    ):
        entry = manager.create_entry(session, content)
        if on_day is not None:
            entry.created_at = datetime.combine(on_day, time(10))
    session.commit()


ASK = {"notes_only": True, "use_tools": False, "answer_from": "notes"}


def test_try_again_on_the_route_rewords_and_keeps_the_lead(client, session):
    _seed(session)
    first = _ask(client, "what have I done for fitness", **ASK)
    again = _ask(client, "what have I done for fitness", attempt=1, **ASK)
    assert first["text"] != again["text"]
    lead = lambda out: (out["grounding"][0]["sentences"][0]["note_id"], out["grounding"][0]["sentences"][0]["start"])  # noqa: E731
    assert lead(first) == lead(again)


def test_a_correction_on_the_route_answers_from_the_note_it_names(client, session):
    # "on Saturday" is the last Saturday, so the notes are dated then: seeded
    # "now" they are found only when the suite happens to run on that day.
    saturday = recognise_questions.question_day("on Saturday", user_now(deps.get_config()).date())[0]
    _seed(session, on_day=saturday)
    first = _ask(client, "what did I do on Saturday", **ASK)
    history = [{"question": "what did I do on Saturday", "answer": first["text"]}]
    fixed = _ask(client, "no, the gym one", history=history, **ASK)
    assert fixed["grounding"][0]["sentences"][0]["sentence"].startswith(("You went to the gym", "I went to the gym")), fixed["text"]


# The floors of CHAT_PLAN Phase 6's five eval sets (decision 40), each set a
# fixture in `fixtures/composer/` written by `scripts/phase6_fixtures.py` with
# its expected values worked out from the row, never from the engine. Floors
# are the first measured run's numbers; a change that lowers one has found
# something real (CLAUDE.md section 7: fix the cause, never the floor).

@functools.cache
def _dialogues() -> dict:
    return _composer_eval.dialogues_summary(_composer_eval.run_dialogues())


def test_insights_fire_on_their_threshold_and_are_rederived():
    got = _composer_eval.insights_summary(_composer_eval.run_insights())
    assert got["rows"] == 40
    assert got["positive_recall"] >= 0.9
    assert got["negatives_silent"] == got["negatives"] == 10
    assert got["measured_rederived"]


def test_dialogues_read_each_terse_turn_and_stay_grounded():
    got = _dialogues()
    assert got["turns"] == 600
    assert got["kind_accuracy"] >= 0.99
    assert all(share >= 0.95 for share in got["by_effect"].values()), got["by_effect"]
    assert got["grounded"]


def test_a_conversation_never_repeats_a_lead_in():
    got = _dialogues()
    assert got["lead_in_repeats_max"] == 0
    assert got["openers_distinct_min"] >= 6


def test_acts_parse_and_no_lookalike_is_an_act():
    got = _composer_eval.acts_summary(_composer_eval.run_acts())
    assert got["acts"] >= 33
    assert got["parse_accuracy"] == 1.0
    assert got["false_positive_acts"] == 0


def test_web_answers_are_spans_of_the_pages_cited_by_url():
    got = _composer_eval.web_summary(_composer_eval.run_web())
    assert got["web_spans"] == got["cited_by_url"] == 1.0
    assert got["first_from_the_right_page"] >= 0.9


def test_each_source_kind_is_cited_as_itself():
    got = _composer_eval.sources_summary(_composer_eval.run_sources())
    assert got["kind_right"] == got["caption_and_quote_right"] == 1.0
    assert got["grounded"]
