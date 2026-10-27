"""The composed answer through `/chat/stream` (INBOX 688).

The Ask box sends `answer_from: "notes"` when "From your notes" is chosen; with
no model running a notes-only turn is composed whatever it sends. The answer
arrives in one piece with exact grounding rows, `meta.composed` says which kind
of answer it is, and no model is called for it.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from pathlib import Path

import pytest

from tessellate.ai import composer, personal, question_noise, reading
from tessellate.entry import manager


#: "the 14th of next month", pinned to the day the note was written (B3).
_NOW = date.today()
NEXT_14 = f"14 {composer._MONTHS[_NOW.month % 12]}" + (f" {_NOW.year + 1}" if _NOW.month == 12 else "")


def _ask(client, question: str, **body) -> dict:
    events: dict[str, list] = {}
    with client.stream("POST", "/chat/stream", json={"question": question, **body}) as response:
        assert response.status_code == 200
        for line in response.iter_lines():
            if line.strip():
                event = json.loads(line)
                events.setdefault(event["type"], []).append(event)
    events["text"] = "".join(e["delta"] for e in events.get("answer", []))
    return events


def _seed(session) -> None:
    manager.create_entry(
        session,
        "# Harbor launch plan\n\nShip the mobile app to the public on 14 November. "
        "Three gates before then: beta feedback closed and the pricing page signed off.",
    )
    manager.create_entry(session, "# Dentist\n\nCheck-up booked for the 21st. Ask about the night guard.")
    session.commit()


def test_from_your_notes_composes_even_with_a_model_running(ai_client, fake_ollama, session):
    _seed(session)
    calls_before = len(fake_ollama.chat_models)
    out = _ask(ai_client, "What is the Harbor launch plan?", notes_only=True, use_tools=False, answer_from="notes")
    meta = out["meta"][0]
    assert meta["composed"] is True
    assert meta["answered_by"] is None
    #: Decision 70: the fact first, said once with its day, not the note's
    #: name over a quote.
    assert out["text"].startswith(f"Ship the mobile app to the public on {NEXT_14}, from your note of")
    assert fake_ollama.librarian_reply not in out["text"]
    #: No model was asked for this answer.
    assert len(fake_ollama.chat_models) == calls_before
    #: One grounding event, the exact rows, not re-grounded after the stream.
    assert len(out["grounding"]) == 1
    rows = out["grounding"][0]["sentences"]
    assert out["grounding"][0]["exact"] is True
    assert rows and all(row["sentence"] in out["text"] for row in rows)
    assert out["grounding"][0]["support"]["low"] is False


def test_the_composed_turn_is_saved_with_its_rows(ai_client, session):
    _seed(session)
    _ask(ai_client, "When is the dentist check-up?", notes_only=True, use_tools=False, answer_from="notes")
    turns = ai_client.get("/ask-history").json()["turns"]
    assert len(turns) == 1
    turn = ai_client.get(f"/ask-history/{turns[0]['id']}").json()
    assert turn["answer"].startswith("Check-up booked for the 21st, from your note of")
    assert any(row["sentence"] == "Check-up booked for the 21st" for row in turn["grounding"])


def test_ai_is_still_the_model_when_a_model_runs(ai_client, fake_ollama, session):
    _seed(session)
    out = _ask(ai_client, "What is the Harbor launch plan?", notes_only=True, use_tools=False, answer_from="ai")
    assert out["meta"][0]["composed"] is False
    assert fake_ollama.librarian_reply in out["text"]


def test_an_unknown_choice_is_the_default_not_an_error(ai_client, fake_ollama, session):
    _seed(session)
    out = _ask(ai_client, "What is the Harbor launch plan?", notes_only=True, use_tools=False, answer_from="xyz")
    assert out["meta"][0]["composed"] is False


def test_with_no_model_the_ask_box_composes(client, session):
    _seed(session)
    out = _ask(client, "What is the Harbor launch plan?", notes_only=True, use_tools=False)
    assert out["meta"][0]["composed"] is True
    assert out["text"].startswith(f"Ship the mobile app to the public on {NEXT_14}")


def test_with_no_model_a_chat_message_is_composed_too(client, session):
    """INBOX 725, the owner: "the composer response should also be able to
    be viewed in chat messages". With no model the Chat tab composes, with
    its exact rows and its own next questions; it used to quote forty-word
    passages under "No model is running"."""
    _seed(session)
    out = _ask(client, "What is the Harbor launch plan?", use_tools=False)
    assert out["meta"][0]["composed"] is True
    assert "No model is running" not in out["text"]
    assert f"Ship the mobile app to the public on {NEXT_14}," in out["text"].split("\n", 1)[0]
    assert len(out["grounding"]) == 1 and out["grounding"][0]["exact"] is True
    assert isinstance(out["grounding"][0]["next"], list)


def test_a_running_model_still_answers_the_chat_tab(ai_client, fake_ollama, session):
    """The owner, 2026-10-06: "the ai still should be used as the chat bot
    when it is available"."""
    _seed(session)
    out = _ask(ai_client, "What is the Harbor launch plan?", use_tools=False)
    assert out["meta"][0]["composed"] is False
    assert fake_ollama.librarian_reply in out["text"]


def test_tell_me_more_is_read_against_the_turn_before(client, session):
    _seed(session)
    first = _ask(client, "What is the Harbor launch plan?", notes_only=True, use_tools=False)
    more = _ask(
        client,
        "tell me more",
        notes_only=True,
        use_tools=False,
        history=[{"question": "What is the Harbor launch plan?", "answer": first["text"]}],
    )
    #: Not the "Ask is for your notes" hint a bare "tell me more" gets: an
    #: answer about the plan, saying what the first one did not.
    assert "hint" not in more and more["meta"][0]["composed"] is True
    said = {row["sentence"] for row in first["grounding"][0]["sentences"]}
    told = {row["sentence"] for row in more.get("grounding", [{}])[0].get("sentences", [])}
    assert not said & told


def test_a_greeting_is_answered_by_the_app_when_answering_from_notes(ai_client, session):
    """Engine probe P2 (2026-10-10): with From your notes chosen, "hey" got no
    answer at all; it gets the app's own reply, as Chat with no model does.
    With the model answering, the Ask box still hints (test_ask_focus)."""
    out = _ask(ai_client, "hey", notes_only=True, use_tools=False, answer_from="notes")
    assert "hint" not in out and out["text"].strip() and "!" not in out["text"]  # the app answers in its own composed welcome (CHAT_PLAN 1353), not one stored line


class _NeedleStandIn:
    """What `tool_fallback.for_tools` hands back when the needle extra is
    installed and no model server runs: something that is not `req.ollama`."""

    def is_running(self) -> bool:
        return True


def test_small_talk_with_only_the_tool_fallback_is_answered_by_the_app(client, session, monkeypatch):
    """The 2026-10-10 triage, decision 8 (routes_chat `conversational`): the
    tools-only extra writes no prose, so "thanks" with no model server is
    answered by `composer.social`, never handed to it, even in Agent mode."""
    from tessellate.ai import tool_fallback

    monkeypatch.setattr(tool_fallback, "for_tools", lambda _primary: _NeedleStandIn())
    out = _ask(client, "thanks", use_tools=True)
    assert out["meta"][0]["answered_by"] is None
    assert out["text"] in composer.SOCIAL["thanks"]


def test_a_notes_question_with_no_model_is_still_composed(client, session, monkeypatch):
    from tessellate.ai import tool_fallback

    monkeypatch.setattr(tool_fallback, "for_tools", lambda _primary: _NeedleStandIn())
    _seed(session)
    out = _ask(client, "When is the dentist check-up?", use_tools=False)
    assert out["meta"][0]["composed"] is True
    assert "Check-up booked for the 21st," in out["text"]


# Read requests reach their tool with no model, in people's words and the
# owner's typos, and the answer carries the links (brief composer item 4: "30
# phrasings, each answer offers the exact action row or nav link").

ROUTING_GOLD = json.loads((Path(__file__).parent / "fixtures" / "composer" / "routing_1011.json").read_text(encoding="utf-8"))
ROUTING_NOW = datetime(2026, 10, 11, 10, 0)
#: Measured 2026-10-11: 12 of 30 read as typed before, 30 of 30 after.
ROUTING_FLOOR = 1.0


def _tool(typed: str) -> str | None:
    return reading.read(question_noise.repair(question_noise.tidy(typed)), now=ROUTING_NOW).tool


def test_the_gold_requests_reach_their_tool():
    misses = [(typed, want, _tool(typed)) for typed, want in ROUTING_GOLD["routes"] if _tool(typed) != want]
    assert len(ROUTING_GOLD["routes"]) >= 30
    assert 1 - len(misses) / len(ROUTING_GOLD["routes"]) >= ROUTING_FLOOR, misses


def test_a_question_about_one_note_is_not_the_whole_list():
    listing = {"list_tags", "list_categories", "list_documents", "list_skills", "list_notes", "notebook_overview", "notebook_structure"}
    wrong = [(typed, _tool(typed)) for typed in ROUTING_GOLD["not_tools"] if _tool(typed) in listing]
    assert not wrong, wrong


def _answer(client, question):
    with client.stream("POST", "/chat/stream", json={"question": question, "use_tools": True}) as response:
        events = [json.loads(line) for line in response.iter_lines() if line.strip()]
    return "".join(e.get("delta", "") for e in events if e["type"] == "answer")


def test_through_the_route_a_typed_request_lists_with_its_links(client, session):
    manager.create_entry(session, "# Dentist\n\nCheck-up booked for the 21st.", tags=["health"])
    manager.create_entry(session, "# Harbor launch\n\nShip the app on the 14th.", tags=["harbor"])
    session.commit()
    tags = _answer(client, "shwo me evry tag i hav plz")
    assert "You have two tags" in tags and "[Open your notes](#/notes)" in tags, tags
    notes = _answer(client, "shwo all my notes")
    assert re.search(r"\]\(#/notes/\d+\)", notes), notes


def test_a_listing_by_category_or_tag_lists_only_those(client, session):
    """Row 442 (P12): "list my work notes" answered "I found two notes about
    list my work"; it lists the Work notes, and a tag the same way."""
    harbor = manager.create_entry(session, "# Harbor launch\n\nShip the app on the 14th.", tags=["harbor"], category_name="Work").id
    standup = manager.create_entry(session, "# Standup\n\nSync rewrite is behind.", tags=["team"], category_name="Work").id
    bread = manager.create_entry(session, "# Sourdough\n\nLoaf 6 was great.", tags=["baking"], category_name="Cooking").id
    session.commit()
    for typed in ("list my work notes", "shw me all my work notes plz", "notes in work"):
        said, rows = _listed(client, typed)
        assert said.startswith("Here are your two Work notes"), said
        assert rows == {harbor, standup}, (typed, rows)
    said, rows = _listed(client, "show my baking notes")
    assert said.startswith("Here is your note tagged #baking") and rows == {bread}, (said, rows)


def _listed(client, question):
    """The answer's words, and the ids of the notes it lists: as rows under
    an act's line, or as links in a read's answer."""
    with client.stream("POST", "/chat/stream", json={"question": question, "use_tools": True}) as response:
        events = [json.loads(line) for line in response.iter_lines() if line.strip()]
    said = "".join(e.get("delta", "") for e in events if e["type"] == "answer")
    rows = {item["id"] for e in events if e["type"] == "tool" for card in e.get("cards") or [] for item in card.get("items") or []}
    return said, rows or {int(n) for n in re.findall(r"\]\(#/notes/(\d+)\)", said)}


# Personal and random questions with no model (brief composer item 8; the
# owner, 2026-10-11: "Can the composer answer personal questions or any other
# random questions??"): about the person, from their notes; about the app or
# the assistant, in its voice; small talk; and general knowledge the offline
# app cannot know, said honestly, never invented.

PERSONAL_GOLD = json.loads((Path(__file__).parent / "fixtures" / "composer" / "personal_1011.json").read_text(encoding="utf-8"))
#: Measured 2026-10-11: 9 of 30 before `ai/personal.py`, 30 of 30 after.
PERSONAL_FLOOR = 1.0


def _ask_personal(client, question):
    with client.stream("POST", "/chat/stream", json={"question": question, "use_tools": False}) as response:
        events = [json.loads(line) for line in response.iter_lines() if line.strip()]
    said = "".join(e.get("delta", "") for e in events if e["type"] == "answer")
    #: How a misspelt question was read is said first, then the answer.
    said = re.sub(r"^I read that as “[^”]*”\.\n\n", "", said)
    return said, [e for e in events if e["type"] == "grounding"]


def test_the_gold_personal_and_random_questions(client, session):
    for note in PERSONAL_GOLD["notes"]:
        manager.create_entry(session, note)
    session.commit()
    misses = []
    for question, lead in PERSONAL_GOLD["questions"]:
        said, _ = _ask_personal(client, question)
        #: A list is a family whose line varies by chat and by day
        #: (`routes_chat._reply_seed`): any of its openings is right.
        if not said.startswith(tuple(lead) if isinstance(lead, list) else lead) or any(n in said for n in PERSONAL_GOLD["never"]) or not said.strip():
            misses.append((question, said[:120]))
    assert len(PERSONAL_GOLD["questions"]) >= 30
    assert 1 - len(misses) / len(PERSONAL_GOLD["questions"]) >= PERSONAL_FLOOR, misses


def test_a_fact_about_the_person_carries_its_note(client, session):
    about = manager.create_entry(session, "# About me\n\nI live in Perth and I work part time at the cafe.").id
    session.commit()
    said, grounding = _ask_personal(client, "where do i live")
    assert said.startswith("You live in Perth, going by your note of")
    row = grounding[0]["sentences"][0]
    assert row["note_id"] == about and row["source"].startswith("I live in Perth")


@pytest.mark.parametrize(
    ("note", "key", "said"),
    [
        ("I live in Perth and I work at the cafe.", "live", "you live in Perth"),
        ("I work as a nurse at St John's.", "work", "you work as a nurse at St John's"),
        ("my birthday is on 3 December", "birthday", "your birthday is 3 December"),
        ("I was born in 1998.", "born", "you were born 1998"),
        ("My dog Biscuit hates the vacuum.", "person", "your dog is Biscuit"),
        ("Coffee with Priya, my boss, at 10.", "person", "your boss is Priya"),
        ("Fav movie is Dune.", "favourite", "your favourite movie is Dune"),
        ("I'm learning Japanese on Duolingo.", "learning", "you're learning Japanese"),
    ],
)
def test_what_a_note_says_of_its_writer(note, key, said):
    found = personal.facts([{"id": 1, "content": note, "created_at": "2026-10-01T10:00:00"}])
    assert any(f.key == key and f.said == said for f in found), [(f.key, f.said) for f in found]


def test_an_age_is_worked_out_from_a_birth_year():
    notes = [{"id": 1, "content": "I was born in 1998.", "created_at": "2026-01-05T10:00:00"}]
    assert personal.answer("how old am i", notes, date(2026, 10, 11))["text"].startswith("You're about 28: you were born in 1998")


def test_a_question_about_someone_else_is_not_personal():
    for question in ("where does sam live", "what did i say about the dentist", "who is jess", "what's the capital of my essay"):
        assert personal.asked(question) is None, question
    assert not personal.general("what did I write about france")
    assert personal.general("whats the capital of france")
    assert not personal.general("who is Sam") and personal.general("who is the president of france")
