"""Hub batch 2 (2026-11-11): the base failures fixed at their cause, then the
found-not-fixed rows. Clock: Monday 9 November 2026, 12:00."""

from __future__ import annotations

import pytest

import tests._seed_bt_1109 as bt
import tests._seed_r9_1109 as r9
from tessellate.ai import composer, composer_recall, composer_story

NOTES = [{"id": 1, "content": "# Boiler\n\nDue in March.", "created_at": "2026-09-01"}]


def test_a_trivia_question_with_a_year_is_not_a_window_on_the_notes():
    assert composer_recall.trivia("who won the cup in 1966")
    said = composer.compose("who won the cup in 1966", NOTES)["text"]
    assert "was written in" not in said and said.endswith("?"), said


def test_a_question_about_my_notes_in_a_year_still_says_nothing_was_written():
    for question in ("what did I write in 1966", "who did I meet in 1999", "which notes are from 1966"):
        assert not composer_recall.trivia(question), question
    assert "1966" in composer.compose("what did I write in 1966", NOTES)["text"]


def test_a_quote_loses_its_hashtags():
    assert composer_story._clean_quote("Kiln firing is on Saturday at 10am. #pottery #hobby") == "Kiln firing is on Saturday at 10am"
    assert composer_story._clean_quote("the #garden is done.") == "the garden is done"


def test_a_date_s_own_figures_are_not_unbacked():
    from tessellate.ai import source_check

    sources = source_check.Sources(["Dentist check-up 2026-11-14T09:30:00", "The current date and time is 2026-11-09"], "what is on")
    for said in ("Your dentist is on Sat 14 Nov at 9:30, in 5 days.", "That is 5 days away."):
        assert source_check.unbacked_claims(said, sources) == [], said
    assert source_check.unbacked_claims("It is in 6 days.", sources) == ["6"]
    weeks = source_check.Sources(["Trip 2026-11-23", "The current date and time is 2026-11-09"], "what is on")
    assert source_check.unbacked_claims("The trip is in 2 weeks.", weeks) == []


@pytest.fixture
def go(client, session, monkeypatch):
    r9.seed(session)
    return r9.asker(client, monkeypatch)


@pytest.fixture
def btask(client, session, monkeypatch):
    bt.seed(session)
    bt.fix_clock(monkeypatch)
    return lambda q: bt.ask(client, q, notes_only=True)["text"]


@pytest.mark.parametrize("question", [
    "are we meeting on Tuesday", "do we have a meeting on tuesday", "is there a meeting on Tuesday", "are we meeting tomorrow",
    "are we meeting on Tuesday?",
])
def test_a_meeting_ask_is_the_days_list_led_by_yes(btask, question):
    said = btask(question)
    assert said.startswith("Yes. ") and "Team sync with Priya" in said, said


@pytest.mark.parametrize("question", ["are we meeting on Wednesday", "is there a meeting on Friday", "do I have a meeting on Wednesday"])
def test_a_meeting_ask_on_a_day_with_none_says_so(btask, question):
    said = btask(question)
    assert said.startswith("No meeting is written for "), said
    assert " on Wednesday" not in said.split(".")[0] and " on Friday" not in said.split(".")[0], said


def test_a_meeting_ask_that_names_a_person_is_not_taken_for_the_day(btask):
    assert not btask("am I meeting Priya on Tuesday").startswith(("Yes. ", "No meeting is written"))


def test_rung_is_said_as_rang(client, session, monkeypatch):
    from datetime import datetime

    import tests._seed_r9_1109 as r9
    from tessellate.entry import manager

    entry = manager.create_entry(session, "Weekend\n\nRung mum about the party. Back Sunday.")
    entry.created_at = datetime(2026, 11, 3, 10)
    session.commit()
    r9.fix_clock(monkeypatch)
    for question in ("when did I phone mum", "when did I ring mum"):
        said = r9.ask(client, question, notes_only=True)["text"]
        assert "you rang mum" in said and "rung" not in said.lower(), said


def test_the_latest_notes_written_at_one_moment_keep_the_searchs_order(session):
    from datetime import datetime

    from tessellate.entry import manager
    from tessellate.search import search_manager
    from tests.test_ai_core import FakeEmbeddingService

    moment = datetime(2026, 11, 2, 9, 0)
    for content in ("Jogging jogging jogging, the knee is fine, long run done", "A note that mentions jogging once"):
        manager.create_entry(session, content).created_at = moment
    session.commit()
    entries, _mode = search_manager.retrieve(session, "latest notes about jogging", FakeEmbeddingService(available=False), limit=5)
    assert [e.content.split(",")[0] for e in entries][0].startswith("Jogging jogging"), [e.content for e in entries]


def test_books_count_the_same_way_however_it_is_asked(go):
    said = [go(q)[0] for q in ("what do I know about books", "what do I have on books", "tell me about books")]
    assert all(text.startswith("You have three notes about books") for text in said), [t[:50] for t in said]


# --- B23: a bare yes takes up a note or checklist offer, the offer being the proposal ---------

CHECKLIST_ANSWER = (
    "Three to read, from your Reading note:\n- [ ] The Overstory\n- [ ] Tomorrow and Tomorrow and Tomorrow\n- [ ] Piranesi\n\nSave it as a checklist note?"
)


def test_a_yes_to_the_checklist_offer_is_a_checklist_note_of_those_lines():
    from tessellate.ai import composer_talk, task_acts

    said = composer_talk.accepted_offer("yes", [{"question": "what do I need to read", "answer": CHECKLIST_ANSWER}])
    assert said, said
    act = task_acts.read_checklist_note(said)
    assert act and act["intent"] == "new_note", (said, act)
    assert act["content"] == "# To read\n\n- [ ] The Overstory\n- [ ] Tomorrow and Tomorrow and Tomorrow\n- [ ] Piranesi", act


def test_a_yes_to_a_pick_or_a_new_list_offer_is_the_note_the_button_makes():
    from tessellate.ai import commands, composer_talk

    pick = composer_talk.accepted_offer("sure", [{"question": "q", "answer": "The first suits you better.\n\nNote the first as your pick?"}])
    assert pick and (got := commands.read(pick, r9.NOW)) and got["intent"] == "new_note" and "My pick: the first" in got["content"], (pick, got)
    start = composer_talk.accepted_offer("yes please", [{"question": "q", "answer": "Two films.\n\nStart a list of films to watch next?"}])
    assert start and (got := commands.read(start, r9.NOW)) and got["intent"] == "new_note" and "Films to watch next" in got["content"] and "- [ ]" in got["content"], (start, got)


def test_a_yes_with_no_offer_behind_it_builds_nothing():
    from tessellate.ai import composer_talk

    assert composer_talk.accepted_offer("yes", [{"question": "q", "answer": "Three to read.\n\nThat is all."}]) is None
    assert composer_talk.accepted_offer("yes but not those", [{"question": "q", "answer": CHECKLIST_ANSWER}]) is None


def test_a_yes_to_the_checklist_offer_saves_the_note_with_undo(client, session, monkeypatch):
    from sqlalchemy import select

    from tessellate.core.database import Entry

    r9.seed(session)
    go = r9.asker(client, monkeypatch, chat=True)
    said, _events = go("what do I need to read")
    assert said.endswith("Save it as a checklist note?")
    before = len(session.scalars(select(Entry)).all())
    reply, events = go("yes", history=[{"question": "what do I need to read", "answer": said}])
    session.expire_all()
    made = [e for e in session.scalars(select(Entry)).all() if "- [ ] Piranesi" in (e.content or "") and e.content.startswith("# To read")]
    assert len(made) == 1 and len(session.scalars(select(Entry)).all()) == before + 1, (reply, events)
    assert "- [ ] Tomorrow and Tomorrow and Tomorrow" in made[0].content
    assert any(e.get("undo") or e.get("type") in ("undo", "done") for e in events), events
