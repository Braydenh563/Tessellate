"""F1 of the composer conversation audit (fable-composer-1110.md): a follow-on
reads what the last answer showed, not the words of the last question.

Each composed answer carries a small frame (the notes it used, the person or
thing it was about, the question it answered, the days it named, its list
lines); the page sends it back on the next turn, and a follow-on binds to it
before anything is searched. With no frame the text reading stays.

No model, clock fixed at Tuesday 10 November 2026, 09:00, the audit's notebook
(`tests/_seed_composer_1110.py`). History is sent as the page sends it: the
last four turns, `objects` from the sources and `frame` from the frame event.
"""

from __future__ import annotations

import json
import re

import pytest

from tessellate.ai import composer, composer_dialogue, composer_talk
from tessellate.api import chat_said, chat_turn, routes_chat
from tessellate.api.chat_request import ChatTurn
from tessellate.core import clock
import tests._seed_composer_1110 as seed

NOW = seed.NOW


@pytest.fixture(autouse=True)
def _fixed_now(monkeypatch):
    for module in (routes_chat, chat_said, chat_turn):
        monkeypatch.setattr(module, "user_now", lambda _config: NOW)
    monkeypatch.setattr(clock, "today", lambda: NOW.date())


def _ask(client, question, history):
    events = []
    with client.stream("POST", "/chat/stream", json={"question": question, "history": history}) as response:
        events = [json.loads(line) for line in response.iter_lines() if line.strip()]
    text = "".join(e.get("delta", "") for e in events if e.get("type") == "answer")
    meta = next((e for e in events if e.get("type") == "meta"), {})
    titles = [str(r.get("title") or r.get("content") or "")[:60] for r in meta.get("raw_results") or []]
    frame = next((e["frame"] for e in events if e.get("type") == "frame"), None)
    cited = [s["note_id"] for e in events if e.get("type") == "grounding" for s in e.get("sentences") or []]
    return {"text": text, "titles": titles, "frame": frame, "cited": cited}


def _talk(client, turns, *, frames=True):
    """Each turn asked with the history the page would send; the answers in order."""
    history, said = [], []
    for question in turns:
        got = _ask(client, question, history[-4:])
        said.append(got)
        turn = {"question": question, "answer": got["text"]}
        objects = [re.split(r"[:.!?]", t.rstrip("…"))[0].strip()[:80] for t in got["titles"]][:5]
        if [o for o in objects if o]:
            turn["objects"] = [o for o in objects if o]
        if frames and got["frame"]:
            turn["frame"] = got["frame"]
        history.append(turn)
    return said


def _lead(text):
    return text.strip().split("\n", 1)[0]


# --- the frame itself -----------------------------------------------------------


def test_a_composed_answer_sends_its_frame(client, session):
    ids = seed.seed(session)
    got = _ask(client, "when is my dentist appointment", [])
    frame = got["frame"]
    assert frame and frame["note_ids"][0] == ids["Dentist"], frame
    assert frame["ask"] == "when is my dentist appointment"
    assert "dentist" in frame["subject"].lower()
    assert "2026-11-21" in frame["dates"], frame
    #: Small: ids, short strings, never a note's body.
    assert len(json.dumps(frame)) < 600
    assert "night guard" not in json.dumps(frame)


def test_a_person_answer_names_the_person(client, session):
    seed.seed(session)
    assert _ask(client, "who is anna", [])["frame"]["person"] == "Anna"
    assert _ask(client, "how much is the budget", [])["frame"]["person"] == ""


def test_the_frame_is_bounded_client_input():
    long = {"note_ids": list(range(40)), "subject": "x" * 500, "person": "y" * 300, "ask": "z" * 900, "dates": ["2026-11-21"] * 30, "items": ["i" * 400] * 40}
    with pytest.raises(ValueError):
        ChatTurn(question="q", answer="a", frame=long)
    turn = ChatTurn(question="q", answer="a", frame={"note_ids": [3], "subject": "dentist", "dates": ["not a date"]})
    assert turn.frame.note_ids == [3] and turn.frame.dates == []


def test_a_frame_scope_is_rechecked_against_the_notebook(client, session):
    """The ids are client input: a deleted or private note is never read through them."""
    from tessellate.entry import manager

    ids = seed.seed(session)
    hidden = manager.create_entry(session, "# Secret\n\nThe locker code is 4512.", category_name="Life")
    hidden.is_private = True
    session.commit()
    frame = {"note_ids": [hidden.id], "subject": "Secret", "person": "", "ask": "what is the secret", "dates": [], "items": []}
    got = _ask(client, "what is in it", [{"question": "what is the secret", "answer": "Nothing.", "frame": frame}])
    assert "4512" not in got["text"]
    assert ids["Dentist"]  # the notebook is the audit's


# --- the nine F1 rows -------------------------------------------------------------


def test_and_kyoto_after_the_budget_is_not_the_budget_again(client, session):
    seed.seed(session)
    said = _talk(client, ["what do I know about the japan trip", "how much is the budget", "and kyoto?"])
    assert said[2]["text"] != said[1]["text"]
    assert "Kyoto" in _lead(said[2]["text"]) or "Kyoto" in said[2]["text"].split("\n\n", 2)[1]
    assert "Budget is $4,500" not in _lead(said[2]["text"])


def test_what_does_she_like_is_the_person_not_her_birthday(client, session):
    seed.seed(session)
    said = _talk(client, ["who is anna", "when is her birthday", "what does she like"])
    assert "pottery" in _lead(said[2]["text"]), said[2]["text"]


def test_who_is_it_with_reads_the_appointment_note(client, session):
    ids = seed.seed(session)
    said = _talk(client, ["when is my dentist appointment", "who is it with"])
    assert "Dr Patel" in _lead(said[1]["text"]), said[1]["text"]
    assert "floss" not in said[1]["text"]
    assert said[1]["cited"] and set(said[1]["cited"]) == {ids["Dentist"]}


def test_summarise_it_then_another_day(client, session):
    seed.seed(session)
    said = _talk(client, ["what did I write last week", "show me the first one", "summarise it", "what about yesterday"])
    assert "Shopping" in said[2]["text"], said[2]["text"]
    assert "“first”" not in said[3]["text"] and "summarise" not in said[3]["text"].lower()
    assert "plumber" in said[3]["text"].lower(), said[3]["text"]


def test_thanks_thats_all_is_not_searched(client, session):
    seed.seed(session)
    said = _talk(client, ["what do I do if it stops working", "thanks that's all"])
    #: Not searched: no note quoted, no words reported missing ("None of these notes mention “stops”").
    assert "mention" not in said[1]["text"] and "[**" not in said[1]["text"] and "Router" not in said[1]["text"], said[1]["text"]


@pytest.mark.parametrize("question", ["where did you get that", "are you sure", "did you get that right"])
def test_a_turn_about_the_answer_is_not_rewritten(question):
    history = [{"question": "when is the stats exam", "answer": "The statistics exam is on 24 November."},
               {"question": "are you sure", "answer": "Yes."}]
    follow = composer.follow_on(question, history)
    assert follow is None or "sure" not in follow.question


def test_what_about_mia_after_a_reminder_asks_of_mia(client, session):
    seed.seed(session)
    said = _talk(client, ["who is anna", "when is she visiting", "remind me about it a week before", "what about mia"])
    assert "it about Mia" not in said[3]["text"] and "about mia before" not in said[3]["text"].lower()
    assert "Mia" in _lead(said[3]["text"]), said[3]["text"]


def test_and_mia_keeps_the_question_then_that_is_hers(client, session):
    seed.seed(session)
    said = _talk(client, ["when is anna's birthday", "and mia", "when is that due"])
    assert "9 February" in _lead(said[1]["text"]), said[1]["text"]
    assert "9 February" in _lead(said[2]["text"]), said[2]["text"]


def test_and_the_other_is_the_other_note_not_a_chart(client, session):
    ids = seed.seed(session)
    said = _talk(client, ["what do I know about harbor", "the first one", "and the other"])
    assert "per tag" not in said[2]["text"] and "chart" not in said[2]["text"].lower()
    assert said[2]["cited"] and ids["Harbor launch plan"] not in said[2]["cited"][:1], said[2]
    assert "Harbor" in said[2]["text"] or "harbor" in said[2]["text"]


# --- bound before searched: the asks that were searched cold -----------------------

#: (the dialogue, the note the last answer must cite first, words its lead must hold)
BOUND = [
    (["how do I make banana bread", "what temperature"], "Banana bread", "175"),
    (["how do I make banana bread", "how much flour"], "Banana bread", "250 g"),
    (["when is the exam", "what room"], "Stats exam", "B204"),
    (["when is the exam", "where is it"], "Stats exam", "B204"),
    (["what do I know about the japan trip", "who am I going with"], "", ""),
]


@pytest.mark.parametrize("turns, note, words", BOUND, ids=[b[0][-1] for b in BOUND])
def test_a_bare_slot_ask_reads_the_last_answers_note(client, session, turns, note, words):
    """Bound to the note the answer before led with (`note`, where the audit named it), never
    searched cold for "temperature" or "fast"."""
    ids = seed.seed(session)
    said = _talk(client, turns)
    assert said[-1]["cited"] and said[-1]["cited"][0] == (ids[note] if note else said[-2]["cited"][0]), said[-1]
    assert words in _lead(said[-1]["text"]), said[-1]["text"]


def test_how_many_days_until_then_takes_the_day_shown(client, session):
    seed.seed(session)
    said = _talk(client, ["when is the exam", "how many days until then"])
    assert "14 days" in said[1]["text"] or "fourteen days" in said[1]["text"], said[1]["text"]


# --- the reading itself, and the text-only fallback ----------------------------------

ANNA = {"note_ids": [8], "subject": "anna", "person": "Anna", "ask": "who is anna", "dates": [], "items": []}
DENTIST = {"note_ids": [6, 7], "subject": "dentist appointment", "person": "", "ask": "when is my dentist appointment", "dates": ["2026-11-21"], "items": []}


@pytest.mark.parametrize("question, read", [
    ("what does she like", "what does Anna like"),
    ("what's her number", "what's Anna's number"),
    ("what should I get her", "what should I get Anna"),
])
def test_a_person_pronoun_is_the_frames_person(question, read):
    follow = composer.follow_on(question, [{"question": "when is her birthday", "answer": "Anna's birthday is 3 December.", "frame": {**ANNA, "ask": "when is Anna's birthday"}}])
    assert follow is not None and follow.question == read


def test_a_thing_pronoun_is_bound_to_the_frames_note():
    follow = composer.follow_on("who is it with", [{"question": "when is my dentist appointment", "answer": "Check-up booked for 21 November.", "frame": DENTIST}])
    assert follow is not None and follow.note_ids == (6,)
    assert "dentist appointment" in follow.question


def test_and_x_swaps_the_frames_person_and_keeps_the_shape():
    follow = composer.follow_on("and mia", [{"question": "when is anna's birthday", "answer": "Anna's birthday is 3 December.", "frame": {**ANNA, "ask": "when is anna's birthday"}}])
    assert follow is not None and follow.question.lower() == "when is mia's birthday"


def test_and_x_keeps_the_shape_with_a_plain_fallback():
    frame = {"note_ids": [11], "subject": "budget", "person": "", "ask": "how much is the budget", "dates": [], "items": []}
    follow = composer.follow_on("and kyoto?", [{"question": "how much is the budget", "answer": "Budget is $4,500.", "frame": frame}])
    assert follow is not None and "the kyoto" not in follow.question.lower()
    assert follow.fallback == "what do my notes say about kyoto?"


def test_with_no_frame_the_text_reading_stays():
    """An older page, or a turn with no composed answer, sends no frame."""
    history = [{"question": "when is my dentist appointment", "answer": "Check-up booked for 21 November."}]
    follow = composer.follow_on("who is it with", history)
    assert follow is not None and follow.kind == "pronoun" and follow.note_ids == ()
    assert composer.follow_on("what temperature", [{"question": "how do I make banana bread", "answer": "Mash the bananas."}]) is None


def test_the_window_follow_on_finds_the_turn_that_had_one():
    history = [{"question": "what did I write last week", "answer": "8 notes last week."},
               {"question": "summarise the shopping note", "answer": "A checklist of four items."}]
    follow = composer.follow_on("what about yesterday", history)
    assert follow is not None and follow.question == "what did I write yesterday?"


def test_a_question_answered_from_a_note_is_not_a_chart():
    history = [{"question": "the first one", "answer": "Ship the Harbor mobile app on 14 December.", "frame": {**DENTIST, "note_ids": [1]}}]
    assert composer_talk.from_history(history, NOW.date()).kind != "window"


def test_the_frame_reads_a_dated_answer():
    frame = composer_dialogue.turn_frame(
        "when is my dentist appointment",
        {"text": "Check-up booked for 21 November at 2:30pm with Dr Patel.", "grounding": [{"note_id": 6, "sentence": "Check-up booked for 21 November at 2:30pm with Dr Patel."}]},
        [{"id": 6, "title": "Dentist", "content": "# Dentist\n\nCheck-up booked for 21 November at 2:30pm with Dr Patel."}],
        NOW.date(),
    )
    assert frame["note_ids"] == [6] and frame["dates"] == ["2026-11-21"] and frame["person"] == ""


#: Found by running the audit's dialogues with frames against the same run without.
@pytest.mark.parametrize("question, ask", [
    ("what about mia", "remind me about the Call with Anna note a week before"),
    ("and after that", "when is Anna visiting"),
])
def test_an_act_or_a_pronoun_is_never_a_person_swap(question, ask):
    follow = composer.follow_on(question, [{"question": ask, "answer": "Anna is visiting on 28 November.", "frame": {**ANNA, "ask": ask}}])
    assert follow is None or follow.kind != "entity", follow


def test_a_month_is_not_a_person():
    lead = {"id": 9, "content": "# Call with Anna\n\nAnna is visiting on 28 November. She wants to try the new ramen place."}
    result = {"text": "Anna is visiting on 28 November.", "grounding": [{"note_id": 9, "sentence": "Anna is visiting on 28 November."}]}
    assert composer_dialogue.turn_frame("the november one", result, [lead], NOW.date())["person"] == ""
