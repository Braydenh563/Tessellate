"""L-chat-92 (A15's eight voice-pattern readers), L-chat-99 (entity card) and the concept table in the
title and tag paths. Synthetic notes, clock fixed at Tuesday 6 October 2026, no model."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from tessellate.ai import composer_entity, composer_study, composer_tables, insight_asks, insights, insights_more
from tests.test_composer_688 import TODAY, _note


def _gym(days_ago: list[int], hour: str = "T07:30:00") -> list[dict]:
    return [_note(i + 1, f"Gym session {i}, legs and a run.", d, tags=["gym"], created_at=(TODAY - timedelta(days=d)).isoformat() + hour) for i, d in enumerate(days_ago)]


def test_streak_names_the_weeks_running():
    notes = _gym([0, 7, 14, 21])
    found = insights.streak("gym", notes, TODAY)
    assert found and "4" in found.text and "gym" in found.text.lower(), found
    assert "week" in insight_asks.answer("what is my gym streak", notes, TODAY).lower()


def test_no_streak_when_the_run_is_broken():
    assert insights.streak("gym", _gym([0, 30, 60]), TODAY) is None


def test_time_of_day_counts_the_notes_that_say_when():
    notes = [_note(i, f"Gym {i}, went in the morning before work.", i * 3, tags=["gym"]) for i in range(1, 5)]
    found = insights_more.time_of_day("gym", notes, TODAY)
    assert found and "4 of 4" in found.text and "morning" in found.text, found


def test_span_gives_the_first_and_last_mention():
    found = insights_more.span("gym", _gym([40, 20, 2]), TODAY)
    assert found and found.slots["subject"] == "gym", found
    assert "first" in found.text.lower() and "last" in found.text.lower()


def test_together_needs_two_shared_notes():
    notes = [_note(1, "Gym with Sam today.", 3, tags=["gym"]), _note(2, "Gym with Sam again.", 6, tags=["gym"]), _note(3, "Gym alone.", 9, tags=["gym"])]
    found = insights_more.together("gym", notes, TODAY)
    assert found and "Sam" in found.text, found
    assert insights_more.together("gym", notes[:1], TODAY) is None


def test_silence_names_a_tag_gone_quiet():
    notes = _gym([80, 70, 62])
    found = insights_more.silence("gym", notes, TODAY)
    assert found and "gym" in found.text.lower(), found
    assert insights_more.silence("gym", _gym([80, 70, 2]), TODAY) is None
    assert any("gym" in i.text.lower() for i in insights_more.quiet_tags(notes, TODAY))


@pytest.mark.parametrize("question", [
    "what is my gym streak", "how long have i been writing about gym", "what goes with gym",
    "what have i stopped writing about lately", "which is my busiest week",
])
def test_every_voice_question_reads_to_a_line_not_a_miss(question):
    notes = _gym([0, 7, 14, 21, 70])
    said = insight_asks.answer(question, notes, TODAY)
    assert said and "!" not in said and chr(0x2014) not in said


def test_an_unrelated_question_is_left_alone():
    assert insight_asks.answer("what is the capital of france", _gym([1]), TODAY) is None


def test_every_template_fills_with_typed_slots():
    for kind in ("time_of_day", "span", "together", "silence"):
        assert kind in composer_tables.INSIGHT_TEMPLATES


# --- entity card ---------------------------------------------------------------------------------------

class _V:
    def __init__(self, id_, content, written):
        self.id, self.note, self.written = id_, {"content": content}, written


def test_the_entity_card_gives_first_last_and_company():
    found = [(_V(1, "Lunch today, with Anna and Tom.", date(2026, 9, 25)), None), (_V(2, "Dinner tonight, with Anna.", date(2026, 10, 3)), None)]
    card = composer_entity.card("Mia", found, TODAY)
    assert card.startswith("First mentioned") and "last" in card and "Anna" in card, card
    assert card.endswith(".") and "!" not in card


def test_the_entity_card_is_empty_when_there_is_nothing_to_add():
    assert composer_entity.card("Mia", [(_V(1, "Hi.", date(2026, 9, 25)), None)], TODAY) == ""


# --- the concept table in the title and tag paths ------------------------------------------------------

@pytest.mark.parametrize("word", ["music", "money", "health", "family", "transport", "clothes"])
def test_the_new_concepts_have_members(word):
    assert len(composer_tables.CONCEPTS[word]) >= 3


def _ctx(notes):
    from datetime import datetime

    return composer_study.Ctx(question="", notes=notes, now=datetime(2026, 10, 6, 9), reminders=[])


def test_a_concept_word_finds_a_note_by_member_in_its_title_and_tag():
    by_title = [_note(1, "# Guitar practice\n\nScales for twenty minutes.", 2), _note(2, "# Errands\n\nPost office.", 3)]
    assert [n["id"] for n in composer_study.topic_notes("music", _ctx(by_title))] == [1]
    by_tag = [_note(1, "Practised scales.", 2, tags=["guitar"]), _note(2, "Post office.", 3)]
    assert [n["id"] for n in composer_study.category_notes("music", _ctx(by_tag))] == [1]
