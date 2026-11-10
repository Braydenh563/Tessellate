"""Second composer audit G12 to G14 and the "should be composed" list: the
patterns short form, the resurfacing reason and name, starter chips, the day
digest's quote and its quiet day, miss lines that do not blame the model, and
the smaller verified faults. Fixed clock."""

from __future__ import annotations

import datetime as dt
from types import SimpleNamespace

import pytest

from tessellate.ai import composer_extra, composer_study, day_digest, insights, notebook_stats, reminder_parser
from tessellate.ai.insights import Insight
from tessellate.api import routes_resurface
from tessellate.entry import meetings
from tessellate.repo import reminders as reminder_repo

NOW = dt.datetime(2026, 11, 10, 10, 0)


def test_patterns_short_form_has_a_capital_and_number_words():
    found = Insight("recurrence", "x", [1], {"subject": "harbor", "count": 5, "since": "3 September"})
    assert insights.short(found) == "Harbor came up five times since 3 September"
    weekly = Insight("streak", "x", [1], {"subject": "golf", "weeks": 3})
    assert insights.short(weekly) == "Golf every week for three weeks"


def test_a_resurfaced_note_says_when_it_is_from_and_that_it_was_not_opened():
    row = SimpleNamespace(age_days=72, link_count=0, access_count=0)
    entry = SimpleNamespace(created_at=dt.datetime(2026, 8, 30))
    assert routes_resurface._reason(row, entry) == "From August, with no links; you have not opened it since."
    assert routes_resurface._reason(SimpleNamespace(age_days=40, link_count=2, access_count=1), SimpleNamespace(created_at=dt.datetime(2026, 10, 1))) == "From October; opened once."


def test_an_untitled_note_is_named_by_six_whole_words():
    name = routes_resurface._name("get a suica card instead of paying cash every single time at the gate")
    assert name == "get a suica card instead of…"
    assert routes_resurface._name("Short title") == "Short title"


def test_a_title_less_note_in_the_day_digest_is_not_quoted_whole():
    long = "remember to look at the suica card options before the trip because the airport counter closes early"
    assert day_digest._head(long) == "remember to look at the suica…"
    assert day_digest._head("# A heading that is rather long indeed, more than eight words in all") .startswith("A heading")


def test_a_quiet_day_names_the_next_thing_coming(session):
    assert day_digest.compose(session, NOW)["empty"] == "Nothing is due and nothing changed since yesterday."
    reminder_repo.create(session, text="Dentist", due_at=dt.datetime(2026, 11, 21, 9, 0), priority="normal")
    session.commit()
    assert day_digest.compose(session, NOW)["empty"] == "Nothing is due today. Next up: Dentist, Saturday 21 November."


def test_the_stats_ask_miss_gives_two_examples_not_the_capability_paragraph():
    from tessellate.ai import stats_ask

    assert stats_ask.HELP_LINE.count("Try") == 1 and len(stats_ask.HELP_LINE.split()) < 25


def test_the_miss_lines_do_not_blame_the_model():
    from tessellate.ai import personal

    said = personal.general_reply(False)
    assert "no model" not in said and "model" not in said
    from tessellate.ai import tool_say

    line, _body, _chips = tool_say._contradictions({"tensions": [], "message": "needs a model"}, {})
    assert "model" not in line


def test_a_reminder_and_a_checklist_line_with_the_same_words_are_one_thing_to_do():
    note = {"id": 3, "content": "Todo\n- [ ] Renew passport\n- [ ] Buy milk", "created_at": "2026-11-01T10:00:00Z", "category": "Life", "tags": []}
    rem = [{"id": 2, "text": "Renew passport", "due_at": dt.datetime(2026, 11, 12, 9), "done": False, "entry_id": 3, "priority": "high"}]
    ctx = composer_study.Ctx(question="what do I need to do", notes=[note], now=NOW, seed="s", asked="what do I need to do", reminders=rem)
    text = composer_extra.answer(ctx).text
    assert text.count("Renew passport") == 1 and "Buy milk" in text
    assert "one reminder and one unticked checklist item" in text


def test_a_note_that_is_only_a_title_has_no_word_count(session):
    from tessellate.entry import manager

    manager.create_entry(session, "# Gift ideas for mum")
    session.commit()
    said = notebook_stats._shortest_notes(session).text
    assert "has only a title" in said and "about 0" not in said


def test_a_one_line_note_is_titled_by_its_only_line():
    assert notebook_stats._has_title("Suica")
    assert not notebook_stats._has_title("Suica\nbuy it at the airport")
    assert notebook_stats._has_title("# Heading\nbody")


def test_the_meeting_card_reads_inline_labelled_lines():
    note = "Standup\nAttendees: Mia, Priya, Jon.\nDecisions: ship Friday; hire Sam.\nActions: Mia sends the deck.\n"
    assert meetings.attendees(note) == ["Mia", "Priya", "Jon"]
    assert meetings.section_items(note, meetings.DECISIONS) == ["ship Friday", "hire Sam"]
    items = meetings.action_items(note)
    assert [i["text"] for i in items] == ["Mia sends the deck"] and items[0]["line"] == 3


def test_a_headed_meeting_is_read_as_before():
    note = "# Standup\n\n## Decisions\n- ship Friday\n\n## Action items\n- [ ] Mia sends the deck\n"
    assert meetings.section_items(note, meetings.DECISIONS) == ["ship Friday"]
    assert [i["text"] for i in meetings.action_items(note)] == ["Mia sends the deck"]


@pytest.mark.parametrize("text, expected", [("something sometime", True), ("do it whenever", True), ("call mum tomorrow", False), ("water the plants", False)])
def test_a_reminder_that_promises_a_time_and_names_none_is_known(text, expected):
    assert reminder_parser.says_no_time(text) is expected


def test_magic_add_refuses_text_with_no_time_word_even_with_a_model_up(client):
    response = client.post("/reminders/parse", json={"text": "something sometime", "tz_offset_minutes": 0})
    assert response.status_code in (422, 503), response.text
    assert "Something sometime" not in str(client.get("/reminders").json())


def test_the_guide_second_sentence_comes_from_the_leading_topic(monkeypatch):
    from tessellate.ai import help_chat

    topics = [
        {"id": "dupes", "body": "Tidy finds duplicate notes. Merge keeps the newest export of each."},
        {"id": "export", "body": "Export your notes from Settings, Data. The export holds every note as Markdown."},
    ]
    answer = help_chat.composed_answer("how do I export my notes", topics, help_chat.guide_lead.Led(topics, "Export your notes from Settings, Data.", steps=False))
    assert "duplicate" not in answer
