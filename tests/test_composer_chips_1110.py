"""F5 of the composer conversation audit (fable-composer-1110.md): the chips under an answer
continue the conversation. They come from the turn's frame (the subject's other facts, the
person, the days, the list rows), never repeat the question just asked or an answer already
given, are grammatical, and are the generic three only when no subject exists. A chip that
acts only proposes: pressing it asks, and the Confirm card does the rest.

Clock fixed at Tuesday 10 November 2026, 09:00; the audit's notebook."""

from __future__ import annotations

import json
import re

import pytest

from tessellate.ai import composer_chips
from tessellate.api import chat_said, chat_turn, routes_chat
from tessellate.core import clock
import tests._seed_composer_1110 as seed

NOW = seed.NOW
GENERIC = {"what did i write this week?", "notebook statistics", "what can you do?"}
#: The broken chips the audit listed: a verb, an adverb or an article where a thing belongs.
BAD = re.compile(r"the Kyoto\b|finish piranesi|latest on (?:read|badly)\b|Priya working|about revise|great run|feeling pretty tired today, slept badly", re.I)


@pytest.fixture(autouse=True)
def _fixed_now(monkeypatch):
    for module in (routes_chat, chat_said, chat_turn):
        monkeypatch.setattr(module, "user_now", lambda _config: NOW)
    monkeypatch.setattr(clock, "today", lambda: NOW.date())


def _turn(client, question, history):
    with client.stream("POST", "/chat/stream", json={"question": question, "history": history[-4:]}) as response:
        events = [json.loads(line) for line in response.iter_lines() if line.strip()]
    text = "".join(e.get("delta", "") for e in events if e.get("type") == "answer")
    chips: list[str] = []
    for e in events:
        offer = e.get("offer") or {}
        if e.get("type") == "offer":
            chips += offer.get("asks") or [a for x in offer.get("also") or [] for a in x.get("asks") or []]
        if e.get("type") == "grounding":
            chips += [str(n) for n in e.get("next") or []]
    frame = next((e["frame"] for e in events if e.get("type") == "frame"), None)
    return {"text": text, "chips": list(dict.fromkeys(chips)), "frame": frame, "events": events}


def _ask(client, question, history=None):
    return _turn(client, question, history or [])


def _then(history, question, got):
    turn = {"question": question, "answer": got["text"]}
    if got["frame"]:
        turn["frame"] = got["frame"]
    return [*history, turn]


@pytest.mark.parametrize("question", ["when are the flights", "when is the exam", "where is the car service", "when is my dentist appointment"])
def test_a_subject_answer_never_ends_with_the_generic_three(client, session, question):
    seed.seed(session)
    chips = _ask(client, question)["chips"]
    assert chips, question
    assert not {c.lower() for c in chips} & GENERIC, chips


def test_a_dated_answer_offers_the_day_not_a_repeat(client, session):
    seed.seed(session)
    chips = _ask(client, "when is the exam")["chips"]
    assert any(c.startswith("Remind me") and c.endswith("the day before") for c in chips), chips
    assert not any(composer_chips.norm(c) == composer_chips.norm("when is the exam") for c in chips)


def test_a_person_answer_offers_what_the_notes_hold_of_them(client, session):
    seed.seed(session)
    chips = _ask(client, "who is anna")["chips"]
    assert "What does Anna like?" in chips, chips
    assert "When is Anna's birthday?" not in chips  # the answer already says it


def test_a_list_answer_offers_a_row_beyond_the_first(client, session):
    seed.seed(session)
    chips = _ask(client, "what do I know about the japan trip")["chips"]
    assert any(c.startswith("What does “") for c in chips) and any(c.startswith("Open ") for c in chips), chips


def test_two_budgets_offer_the_comparison(client, session):
    seed.seed(session)
    assert "Which is higher?" in _ask(client, "compare october and november budget")["chips"]


def test_a_clarifying_question_offers_its_answers(client, session):
    seed.seed(session)
    got = _ask(client, "remind me to call ana")
    assert got["chips"] == ["Tomorrow at 9", "Friday afternoon", "In an hour"], got["chips"]
    #: Pressing one asks; the reply is a card or a confirmation line, never a refusal.
    follow = _ask(client, "Friday afternoon", _then([], "remind me to call ana", got))
    assert "call ana" in follow["text"].lower() or any(e.get("type") == "act" for e in follow["events"]), follow["text"]


def test_the_generic_three_stay_on_a_first_turn_with_no_subject(client, session):
    seed.seed(session)
    assert {c.lower() for c in _ask(client, "how many notes do I have")["chips"]} & GENERIC


@pytest.mark.parametrize("opening", ["what is the latest on the japan trip", "what's the latest on Harbor", "when is the exam", "who is anna", "what do I know about the dentist"])
def test_pressing_every_chip_never_loops_or_stumps(client, session, opening):
    """The walk the audit made (a21, a22): each chip pressed once in order, none repeated, none an
    answer already given, none stumped, none ungrammatical."""
    seed.seed(session)
    history, said, pressed = [], [], []
    got = _ask(client, opening)
    history, said = _then(history, opening, got), [composer_chips.lead(got["text"])]
    queue = [c for c in got["chips"] if not c.startswith("Open ")]
    for _ in range(6):
        if not queue:
            break
        chip = queue.pop(0)
        assert chip not in pressed and (chip.startswith("Open ") or not BAD.search(chip)), (chip, pressed)
        pressed.append(chip)
        got = _ask(client, chip, history)
        lead = composer_chips.lead(got["text"])
        assert lead not in said, (chip, lead)
        assert not re.match(r"(?:I could not find|None of these|Nothing in your notes|That's general knowledge)", got["text"]), (chip, got["text"][:80])
        said.append(lead)
        history = _then(history, chip, got)
        #: "What's the latest on X?" and "What is the latest on X?" are one question.
        seen = {composer_chips.norm(c) for c in [*pressed, *queue]}
        queue += [c for c in got["chips"] if not c.startswith("Open ") and composer_chips.norm(c) not in seen]


@pytest.mark.parametrize("question", ["and the kyoto part", "did I finish piranesi", "what did I read", "how badly did the run go", "is priya working on pricing", "feeling pretty tired today, slept badly"])
def test_no_chip_is_built_from_a_verb_or_an_adverb(client, session, question):
    seed.seed(session)
    for chip in _ask(client, question)["chips"]:
        assert chip.startswith("Open ") or not BAD.search(chip), (question, chip)


@pytest.mark.parametrize("chip, kept", [
    ("What else have I saved about the Kyoto?", "What else have I saved about Kyoto?"),
    ("When did I write about finish piranesi?", ""),
    ("What is the latest on read?", ""),
    ("What's the latest on badly?", ""),
    ("What is the latest on the japan trip?", "What is the latest on the japan trip?"),
    ("Open “Kyoto ideas”", "Open “Kyoto ideas”"),
])
def test_clean_keeps_a_thing_the_notes_name(chip, kept):
    vocab = {"kyoto", "idea", "japan", "trip", "piranesi", "reading", "list"}
    assert composer_chips.clean(chip, vocab, {"kyoto idea"}) == kept


def test_a_model_draft_gets_the_same_chips(ai_client, fake_ollama, session):
    """Parity: the composed draft under a model's answer (`composed_preview`) is chipped like the
    no-model answer: the frame's questions, no generic three."""
    seed.seed(session)
    body = {"question": "when is the exam", "history": [], "use_tools": False}
    with ai_client.stream("POST", "/chat/stream", json=body) as response:
        events = [json.loads(line) for line in response.iter_lines() if line.strip()]
    preview = next(e for e in events if e["type"] == "composed_preview")
    assert any(c.startswith("Remind me") for c in preview["next"]), preview["next"]
    assert not {c.lower() for c in preview["next"]} & GENERIC


def test_a_reminder_asking_when_offers_its_times_with_a_model_up_too(ai_client, fake_ollama, session):
    seed.seed(session)
    with ai_client.stream("POST", "/chat/stream", json={"question": "remind me to call ana", "history": [], "use_tools": False}) as response:
        events = [json.loads(line) for line in response.iter_lines() if line.strip()]
    asks = [a for e in events if e.get("type") == "offer" for a in (e["offer"].get("asks") or [])]
    assert any(composer_chips.asks_time(str(e.get("delta"))) for e in events), events
    assert asks == composer_chips.TIME_CHIPS, asks


def test_a_chip_that_acts_only_proposes(client, session):
    """Pressing "Remind me about X the day before" asks or shows a card; nothing is written until the person confirms."""
    from sqlalchemy import func, select

    from tessellate.core.database import Reminder

    seed.seed(session)
    got = _ask(client, "when is my dentist appointment")
    chip = next(c for c in got["chips"] if c.startswith("Remind me"))
    before = session.scalar(select(func.count()).select_from(Reminder))
    follow = _ask(client, chip, _then([], "when is my dentist appointment", got))
    assert follow["text"] or any(e.get("type") == "act" for e in follow["events"])
    session.expire_all()
    assert session.scalar(select(func.count()).select_from(Reminder)) == before


def test_the_day_before_chip_names_what_it_is_for(client, session):
    """The chip says "about Dentist"; the next turn must not ask what the reminder is for."""
    seed.seed(session)
    got = _ask(client, "when is my dentist appointment")
    chip = next(c for c in got["chips"] if c.startswith("Remind me"))
    follow = _ask(client, chip, _then([], "when is my dentist appointment", got))
    assert "What is the reminder for" not in follow["text"], follow["text"]
    assert "What should the reminder say" not in follow["text"], follow["text"]


@pytest.mark.parametrize("thanks", ["thanks", "thank you", "cheers"])
def test_small_talk_after_an_answer_picks_up_its_chips(client, session, thanks):
    seed.seed(session)
    got = _ask(client, "when is my dentist appointment")
    follow = _ask(client, thanks, _then([], "when is my dentist appointment", got))
    assert any(c.startswith("Remind me about Dentist") for c in follow["chips"]), follow["chips"]


def test_small_talk_with_nothing_before_it_has_no_borrowed_chips(client, session):
    seed.seed(session)
    assert _ask(client, "thanks")["chips"] == []


def test_small_talk_picks_up_the_chips_with_a_model_up_too(ai_client, fake_ollama, session):
    seed.seed(session)
    frame = {"note_ids": [6], "subject": "dentist", "person": "", "ask": "when is my dentist appointment", "dates": ["2026-11-21"], "items": []}
    first = {"question": "when is my dentist appointment", "answer": "Check-up booked for 21 November.", "frame": frame}
    with ai_client.stream("POST", "/chat/stream", json={"question": "thanks", "history": [first], "use_tools": False}) as response:
        events = [json.loads(line) for line in response.iter_lines() if line.strip()]
    asks = [a for e in events if e.get("type") == "offer" for a in (e["offer"].get("asks") or [])]
    assert any(a.startswith("Remind me about") for a in asks), events


def test_last_wrote_states_a_date_and_the_latest_does_not_repeat_it(client, session):
    seed.seed(session)
    last = _ask(client, "When did I last write about Harbor?")
    latest = _ask(client, "What's the latest on Harbor?")
    assert "You last wrote about Harbor on 6 November" in last["text"], last["text"]
    assert last["text"] != latest["text"]
    grounded = [e for e in last["events"] if e.get("type") == "grounding"]
    assert grounded and not grounded[0]["support"]["unsupported"], grounded


def test_what_else_is_on_that_week_is_offered_and_answered(client, session):
    seed.seed(session)
    got = _ask(client, "when is my dentist appointment")
    assert "What else is on that week?" in got["chips"], got["chips"]
    follow = _ask(client, "What else is on that week?", _then([], "when is my dentist appointment", got))
    assert "Decision due by 20 November" in follow["text"] and "Check-up booked" in follow["text"], follow["text"]


@pytest.mark.parametrize("then, window", [("and the week before?", "26 October to 1 November"), ("and the week after?", "9 November to 15 November")])
def test_a_window_moves_off_the_one_before(client, session, then, window):
    """F13 h: "and the week before" is the question before over the week earlier."""
    seed.seed(session)
    got = _ask(client, "what did I write last week")
    assert window in _ask(client, then, _then([], "what did I write last week", got))["text"]


@pytest.mark.parametrize("question", ["summarise my japan notes", "summarise harbor"])
def test_a_summary_of_several_notes_is_one_shape(client, session, question):
    """F13 i: a subject several notes are about (by tag as by title) is the short version of each, never one note and 'Say more'."""
    seed.seed(session)
    text = _ask(client, question)["text"]
    assert text.startswith("Here are your 4 matching notes") or text.startswith("4 notes match"), text
    assert "Say “more”" not in text
    assert not re.search(r"\]\(#/notes/\d+\): [.:;,]", text), text  # no stranded full stop where a title was cut
