"""Second-eye review 2026-10-30 (fable-eye-1030): each test pins a class, asked
three to six ways, with the model off (the composed route)."""

from __future__ import annotations

import contextvars
import json
from datetime import datetime

import pytest

from tessellate.ai import composer_digest
from tessellate.api import routes_chat
from tessellate.core import config
from tessellate.entry import manager

NOW = datetime(2026, 10, 30, 12, 0)


def _note(session, title: str, day: str, body: str, tags: list[str] | None = None) -> None:
    entry = manager.create_entry(session, f"# {title}\n\n{body}", category_name="Journal", tags=tags or [])
    entry.created_at = entry.updated_at = datetime.fromisoformat(day + "T09:00:00")
    session.commit()


@pytest.fixture
def ask(client, session, monkeypatch):
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)

    def go(question: str) -> dict:
        text, rows = "", []
        with client.stream("POST", "/chat/stream", json={"question": question, "use_tools": False}) as response:
            for line in response.iter_lines():
                if not line.strip():
                    continue
                event = json.loads(line)
                if event["type"] == "answer":
                    text += event["delta"]
                elif event["type"] == "grounding":
                    rows = event.get("sentences") or rows
        return {"text": text, "rows": rows}

    return go


@pytest.fixture
def admin(session):
    _note(session, "Admin bits", "2026-10-20", "- [ ] Renew library membership - due 28 October.\n- [ ] Back up laptop - due 2 November.\n- [x] Email the landlord")
    _note(session, "Membership sorted", "2026-10-29", "Renewed my library membership today.")


@pytest.mark.parametrize("question", [
    "Is renewing the library membership still on my list?",
    "Is the library membership still outstanding?",
    "Is renewing the library membership still open?",
])
def test_f3_done_in_a_later_note_is_said_as_that_note_not_a_ticked_box(ask, admin, question):
    said = ask(question)["text"]
    assert "ticked off" not in said, said
    assert "29 October" in said or "Membership sorted" in said, said
    assert "unticked" in said or "still" in said, said


@pytest.mark.parametrize("question", [
    "What's still open in Admin bits?",
    "What is left on Admin bits?",
    "What's still on my Admin bits list?",
])
def test_f3_the_open_list_agrees_with_the_done_note(ask, admin, question):
    said = ask(question)["text"]
    assert "Back up laptop" in said, said
    assert "Renew library membership" not in said or "29 October" in said, said


@pytest.mark.parametrize("question", [
    "When is the laptop backup due?",
    "When do I need to back up the laptop?",
    "What is due on the laptop backup?",
])
def test_f15_no_reminder_offer_for_a_task_a_later_note_records_done(ask, admin, question):
    said = ask(question)["text"]
    assert "Remind you to renew" not in said, said


@pytest.fixture
def sams(session):
    _note(session, "Work people", "2026-10-01", "Sam Patel is my manager and runs the Tuesday planning meeting.", ["work"])
    _note(session, "Family", "2026-10-05", "Sam Hoyle is my cousin who lives in Perth.", ["family"])
    _note(session, "Office news", "2026-10-09", "Sam wants PTO requests in by the 15th.", ["work"])


@pytest.mark.parametrize("question", ["Who is Sam?", "Who's Sam?", "who is sam", "Tell me about Sam."])
def test_f2_who_is_cites_each_note_a_line_came_from(ask, sams, question):
    got = ask(question)
    assert "cousin" in got["text"] and "PTO" in got["text"] and "manager" in got["text"], got["text"]
    by_word = {"cousin": 2, "PTO": 3, "manager": 1}
    assert len(got["rows"]) == 3, got["rows"]
    for row in got["rows"]:
        word = next(w for w in by_word if w in row["source"])
        assert row["note_id"] == by_word[word], row


@pytest.fixture
def hobart(session):
    _note(session, "Hobart flight", "2026-10-14", "Booked the return flight to Hobart for 14 November.", ["hobart", "travel"])
    _note(session, "Hobart hotel", "2026-10-15", "Hotel in Hobart is near the waterfront.", ["hobart", "travel"])
    _note(session, "Hobart food", "2026-10-16", "Want to try the oyster place in Hobart.", ["hobart"])
    _note(session, "Hobart packing", "2026-10-17", "Pack a warm jacket for Hobart.", ["hobart"])
    _note(session, "Hobart budget", "2026-10-18", "The Hobart budget is $900.", ["hobart"])
    _note(session, "Money rules", "2026-09-01", "Don't count the balance as spending yet.", ["money"])
    _note(session, "Hobart maps", "2026-10-19", "Saved a walking map of Hobart.", ["hobart"])


@pytest.mark.parametrize("question", [
    "Count my notes about Hobart.",
    "How many notes do I have about Hobart?",
    "Do I have notes about Hobart?",
    "How much have I written about Hobart?",
    "List my notes about Hobart.",
    "Check my notes about Hobart.",
])
def test_f10_a_many_note_topic_is_never_called_one_note(ask, hobart, question):
    said = ask(question)["text"]
    assert "just the one note" not in said and "only note" not in said, said


def _view(i, title, body, tags):
    stamp = f"2026-10-1{i}T09:00:00"
    return {"id": i, "source_id": i, "title": title, "content": f"# {title}\n\n{body}", "tags": tags, "category": "Journal", "created_at": stamp, "updated_at": stamp}


HOBART = [
    _view(1, "Hobart flight", "Booked the return flight to Hobart.", ["hobart"]),
    _view(2, "Hobart hotel", "Hotel in Hobart is near the waterfront.", ["hobart"]),
    _view(3, "Hobart food", "Don't count the balance as spending yet in Hobart.", ["hobart"]),
    _view(4, "Hobart maps", "Saved a walking map of Hobart.", ["hobart"]),
]


@pytest.mark.parametrize("question", [
    "Count my notes about Hobart.",
    "Check my notes about Hobart.",
    "Tally my notes about Hobart",
    "Count the notes I have about Hobart",
])
def test_f10_a_verb_that_asks_is_not_a_word_to_find(question):
    said = composer_digest.answer(question, HOBART, today=NOW.date())["text"]
    assert "four notes about Hobart." in said and ".." not in said, said
    assert "just the one note" not in said and "only note" not in said, said


def test_f10_one_member_of_a_many_note_topic_is_not_the_only_note():
    said = composer_digest.answer("What did I count in Hobart?", HOBART, today=NOW.date())["text"]
    assert "only note" not in said and "just the one note" not in said, said


@pytest.mark.parametrize(("question", "lead"), [
    ("Is the library membership renewed?", "Yes"),
    ("Was the library membership renewed?", "Yes"),
    ("Has the library membership been renewed?", "Yes"),
    ("Is my library membership renewed yet?", "Yes"),
    ("Is the laptop backed up?", "Not yet"),
    ("Has the laptop been backed up yet?", "Not yet"),
    ("Is the landlord emailed?", "Yes"),
])
def test_f9_a_passive_question_reads_the_checklist_like_did_i(ask, admin, question, lead):
    said = ask(question)["text"]
    assert said.startswith(lead), said
    if lead == "Yes" and "landlord" not in question:
        assert "29 October" in said, said
    if lead == "Not yet":
        assert "Back up laptop" in said, said


@pytest.mark.parametrize("voice", ["professional", "playful", "plain"])
def test_f7_an_answer_leaves_no_state_for_the_next(voice):
    """The digest's context variables are set per answer and must not outlive
    it: the next answer in the same context reads only its own."""
    first = composer_digest.answer("Check my notes about Hobart.", HOBART, today=NOW.date(), voice=voice, turn=7)
    assert first is not None
    assert composer_digest._VOICE.get() == "natural"
    assert composer_digest._VIEWS.get() == []
    assert composer_digest._NAMES.get() == set()
    after = composer_digest.answer("Who is Sam?", [], today=NOW.date())
    assert after is None
    assert composer_digest._VOICE.get() == "natural" and composer_digest._TURN.get() == 0
    alone = contextvars.copy_context().run(composer_digest.answer, "Count my notes about Hobart.", HOBART, today=NOW.date())
    then = composer_digest.answer("Count my notes about Hobart.", HOBART, today=NOW.date())
    assert alone["text"] == then["text"]


def test_f7_tell_me_more_says_all_said_in_the_voice_it_was_given():
    natural = composer_digest.all_said("Check my notes about Hobart", HOBART, today=NOW.date())
    other = next(v for v in composer_digest.VOICES if v != "natural")
    voiced = composer_digest.all_said("Check my notes about Hobart", HOBART, today=NOW.date(), voice=other)
    assert natural and voiced
    assert composer_digest._VOICE.get() == "natural"


def test_f8_tell_me_more_does_not_answer_the_earlier_question_again(client, session, monkeypatch):
    """The answer before wrote its grounding rows; a "more" turn reads those
    instead of answering up to three earlier questions over every note again."""
    _note(session, "Harbor launch plan", "2026-10-01", "Ship the mobile app to the public on 14 November. Beta feedback closed first.")
    _note(session, "Dentist", "2026-10-02", "Check-up booked for the 21st. Ask about the night guard.")
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)
    asked = []
    real = composer_digest.answer
    monkeypatch.setattr(routes_chat.composer_digest, "answer", lambda q, *a, **k: asked.append(q) or real(q, *a, **k))

    def post(question, **body):
        text = ""
        with client.stream("POST", "/chat/stream", json={"question": question, "use_tools": False, "notes_only": True, **body}) as response:
            for line in response.iter_lines():
                if line.strip() and (event := json.loads(line))["type"] == "answer":
                    text += event["delta"]
        return text

    first = post("What is the Harbor launch plan?")
    before = asked.count("What is the Harbor launch plan?")
    post("tell me more", history=[{"question": "What is the Harbor launch plan?", "answer": first}])
    assert asked.count("What is the Harbor launch plan?") == before, asked


def _spending(session):
    _note(session, "Lamp", "2026-10-02", "Paid $100 for the lamp.", ["home"])
    _note(session, "Train", "2026-10-05", "Paid $50 for the train ticket.", ["travel"])
    _note(session, "Boiler", "2026-10-08", "Paid $400 for the boiler repair.", ["home"])


@pytest.mark.parametrize("question", [
    "How much have I spent?",
    "How much did I spend in total?",
    "What is the total of what I have spent?",
])
def test_f6_money_with_a_model_on_is_written_from_the_engines_sum(ai_client, fake_ollama, session, monkeypatch, question):
    """Model on: the sum is the engine's, handed over as facts; the model's
    prose with a figure the engine did not give is refused and the engine's
    own answer stands. Model off: the same sum."""
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)
    _spending(session)
    fake_ollama.librarian_reply = "Altogether you spent $999 on three things."
    text = ""
    with ai_client.stream("POST", "/chat/stream", json={"question": question, "use_tools": False}) as response:
        for line in response.iter_lines():
            if line.strip() and (event := json.loads(line))["type"] == "answer":
                text += event["delta"]
    prompt = "\n".join(str(m.get("content") or "") for m in fake_ollama.chat_calls[-1])
    assert "$550" in prompt, prompt
    assert "$999" not in text and "$550" in text, text


@pytest.mark.parametrize("question", [
    "Did I renew the library membership?",
    "Is the library membership renewed?",
    "Is renewing the library membership still on my list?",
])
def test_f6_a_checklist_answer_with_a_model_on_hands_the_model_the_engines_line(ai_client, fake_ollama, session, monkeypatch, question):
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)
    _note(session, "Admin bits", "2026-10-20", "- [ ] Renew library membership - due 28 October.\n- [ ] Back up laptop - due 2 November.")
    _note(session, "Membership sorted", "2026-10-29", "Renewed my library membership today.")
    fake_ollama.librarian_reply = "Yes, that one is sorted."
    with ai_client.stream("POST", "/chat/stream", json={"question": question, "use_tools": False}) as response:
        list(response.iter_lines())
    prompt = "\n".join(str(m.get("content") or "") for m in fake_ollama.chat_calls[-1])
    assert "29 October" in prompt, prompt


def _old(pattern):
    """The pattern as it was before F14: no lookbehind on a whitespace run, no possessive lead."""
    import re

    source = pattern.pattern.replace("(?<!\\s)", "").replace("(?<![\\s,;:])", "").replace("\\s*+", "\\s*")
    return re.compile(source, pattern.flags)


def _f14_patterns():
    from tessellate.ai import activity, composer, composer_frame, recognise, task_acts

    return {
        "compare-than": composer._COMPARE_SIDES[0],
        "digest-compare": composer_digest._ASKS["compare"],
        "done-tail": task_acts._DONE_TAIL,
        "date-stub": activity._DATE_STUB,
        "presented-end": composer_frame._PRESENTED_END,
        "tail-kind": task_acts._TAIL_KIND,
        "clock-tail": recognise._CLOCK_TAIL,
    }


@pytest.mark.parametrize("name", sorted(_f14_patterns()))
@pytest.mark.parametrize("text", [" " * 20000, "a" + " " * 20000, "a" + " " * 20000 + "x", " " * 20000 + "or", ("a " * 3 + " " * 300) * 60])
def test_f14_the_compare_and_tail_patterns_are_linear_on_blanks(name, text):
    import time

    pattern = _f14_patterns()[name]
    started = time.perf_counter()
    pattern.search(text)
    assert time.perf_counter() - started < 0.1, name


@pytest.mark.parametrize("name", sorted(_f14_patterns()))
def test_f14_the_rewrites_read_exactly_what_the_old_patterns_read(name):
    import random

    new = _f14_patterns()[name]
    old = _old(new)
    pieces = [" ", "  ", "a", "or", "than", "better", "is", "done", "task", "at", "5pm", "9:30", ",", ".", "that", "?", "the", "x"]
    rng = random.Random(14)
    for _ in range(3000):
        text = "".join(rng.choice(pieces) for _ in range(rng.randint(0, 9)))
        a, b = new.search(text), old.search(text)
        assert (a and (a.span(), a.groupdict())) == (b and (b.span(), b.groupdict())), (name, text)


@pytest.mark.parametrize(("content", "name"), [
    ("[ ] Renew library membership - due 28 October.\n[x] Email the landlord", "Renew library membership - due 28 October"),
    ("- [x] Email the landlord\n- [ ] Renew", "Email the landlord"),
    ("- Renew library membership\n- Back up laptop", "Renew library membership"),
    ("1. Renew library membership today\n2. Back up", "Renew library membership today"),
    ("**Admin bits**\nRenew membership", "Admin bits"),
    ("# Admin bits\n\n- [ ] Renew", "Admin bits"),
    ("---\ntags: [admin]\n---\n\n## **Admin bits** ##\nx", "Admin bits"),
    ("__Admin bits__\n[ ] Renew", "Admin bits"),
])
def test_f13_one_reader_names_a_note_the_same_way_for_every_surface(content, name):
    """The sources column, the chips, the study decks and the act cards all
    name a note through `composer_frame.note_title`."""
    from tessellate.ai import commands, composer_frame, study, tool_say

    assert composer_frame.note_title(content) == name
    assert composer_frame.note_title({"content": content}) == name
    assert study.title_of(content) == name
    assert tool_say._name(content) == name
    entry = type("E", (), {"content": content})()
    assert composer_frame.note_title(entry.content, size=48) == name
    assert commands.note_title(entry.content, size=48) == name


def test_f13_a_note_with_no_words_has_no_name():
    from tessellate.ai import composer_frame, tool_say

    assert composer_frame.note_title("") == "" and composer_frame.note_title("  \n\n") == ""
    assert tool_say._name("") == "Untitled"


def test_f13_no_second_reader_of_a_notes_name_in_ai():
    """A new `def _title` is a ninth way to name a note: use
    `composer_frame.note_title`. These three are not readers of a title from
    text: the engine's split of a note into title and body, the view's own
    name (it names a title-less list by its filing), and the questions row's
    first sentence with its stop (pinned by test_quadratic_scans)."""
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "src" / "tessellate" / "ai"
    found = {p.name for p in root.glob("*.py") if re.search(r"^def _title\(", p.read_text(encoding="utf-8"), re.M)}
    assert found == {"composer.py", "composer_lists.py", "questions.py"}, found
