"""With a model up, the model writes every answer and the engine only hands it
facts (CHAT_PLAN decision 75; the owner, 2026-10-27: "why is it responding as
the composer when my ai is in use?? I want the ai to be able to do what the
composer can do but better"). "What is due?" in the popup agent was answered
by the composer's reminder list with the model running: no "Asked <model>"
line, the no-model badge.

The engine's exact answer (the due list, a count, a worked sum) goes into the
model's prompt as facts; its structured parts (the list, the chart, the
panel) still ride under the reply; prose that states a number the facts do
not hold is refused and the engine's own words stand. With no model the
engine answers as before.
"""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from tessellate.api import routes_chat
from tessellate.core.database import Entry, Reminder

#: A fixed clock (CLAUDE.md section 8), Tuesday 27 October 2026, 9:30.
NOW = datetime(2026, 10, 27, 9, 30)
DUE = (("call mum", datetime(2026, 10, 28, 9, 0)), ("pay rent", datetime(2026, 10, 29, 10, 0)), ("book dentist", datetime(2026, 10, 30, 11, 0)))


@pytest.fixture()
def fixed_clock(monkeypatch):
    monkeypatch.setattr(routes_chat, "user_now", lambda _config=None: NOW)


def _seed(session, reminders: bool = True) -> None:
    for text in ("Boiler pressure is low", "Gym plan for the week", "Sourdough starter feeding"):
        session.add(Entry(content=text))
    if reminders:
        for text, due in DUE:
            session.add(Reminder(text=text, due_at=due))
    session.commit()


def _stream(client, question: str, use_tools: bool) -> tuple[list, str]:
    events = []
    with client.stream("POST", "/chat/stream", json={"question": question, "use_tools": use_tools}) as response:
        for line in response.iter_lines():
            if line.strip():
                events.append(json.loads(line))
    return events, "".join(e.get("delta", "") for e in events if e["type"] == "answer")


def _last_meta(events: list) -> dict:
    return [e for e in events if e["type"] == "meta"][-1]


def _prompt(fake) -> str:
    return "\n".join(str(m.get("content") or "") for m in fake.chat_calls[-1])


#: Chat's Ask mode (no tools) and the popup agent (`palette.js` streams
#: `/chat/stream` with `useTools: true`): one route, both surfaces.
SURFACES = pytest.mark.parametrize("use_tools", [False, True], ids=["chat", "popup-agent"])


@SURFACES
def test_what_is_due_is_written_by_the_model_from_the_due_rows(ai_client, fake_ollama, session, fixed_clock, use_tools):
    _seed(session)
    fake_ollama.librarian_reply = "Three things are waiting, and call mum comes first."
    events, answer = _stream(ai_client, "What is due?", use_tools)
    assert fake_ollama.chat_calls, "the model was never asked"
    prompt = _prompt(fake_ollama)
    for text, _due in DUE:
        assert text in prompt, (text, prompt)
    assert answer.startswith(fake_ollama.librarian_reply), answer
    #: The list rides under the reply as the engine drew it: the model wrote
    #: the words, not the table.
    for text, _due in DUE:
        assert text in answer.split(fake_ollama.librarian_reply, 1)[1], answer
    meta = _last_meta(events)
    assert meta["answered_by"] and meta["composed"] is False
    assert any(e["type"] == "stats" and e.get("model") for e in events)


@SURFACES
def test_how_many_notes_is_written_by_the_model_with_the_count(ai_client, fake_ollama, session, fixed_clock, use_tools):
    _seed(session, reminders=False)
    fake_ollama.librarian_reply = "Your notebook holds 3 notes so far."
    events, answer = _stream(ai_client, "How many notes do I have?", use_tools)
    assert fake_ollama.chat_calls, "the model was never asked"
    assert "3 notes" in _prompt(fake_ollama)
    assert fake_ollama.librarian_reply in answer
    assert _last_meta(events)["answered_by"]


@SURFACES
def test_a_worked_sum_is_written_by_the_model_with_the_result(ai_client, fake_ollama, session, fixed_clock, use_tools):
    fake_ollama.librarian_reply = "That comes to 84."
    events, answer = _stream(ai_client, "what is 12 * 7", use_tools)
    assert "84" in _prompt(fake_ollama)
    assert answer == "That comes to 84."
    assert _last_meta(events)["answered_by"]
    #: The worked answer's calculator still rides under it (INBOX 1300 C06).
    assert [e["panel"] for e in events if e["type"] == "panel"] == ["calculator"]


@SURFACES
def test_prose_that_contradicts_the_facts_is_refused(ai_client, fake_ollama, session, fixed_clock, use_tools):
    """A 1.5B model said "two reminders" when there were three (2026-10-12,
    `test_reminders_with_model.py`): the engine's own words stand instead,
    and no model is named under them."""
    _seed(session)
    fake_ollama.librarian_reply = "You have two reminders."
    events, answer = _stream(ai_client, "What is due?", use_tools)
    assert fake_ollama.chat_calls
    assert "two reminders" not in answer
    for text, _due in DUE:
        assert text in answer
    assert _last_meta(events)["answered_by"] is None
    assert not any(e["type"] == "stats" and e.get("model") for e in events)


def test_a_refused_reply_streams_none_of_its_thinking(ai_client, fake_ollama, session, fixed_clock):
    """The thinking of a reply that is then refused was streamed before the
    check (the review of 2026-10-27): it is held with the prose, dropped on a
    refusal, and the tokens it cost are still reported, with no model named."""
    _seed(session)
    fake_ollama.librarian_thinking = "Counting two reminders."
    fake_ollama.librarian_reply = "You have two reminders."
    events, _answer = _stream(ai_client, "What is due?", True)
    assert not [e for e in events if e["type"] == "thinking"]
    stats = [e for e in events if e["type"] == "stats"]
    assert stats and not any(e.get("model") for e in stats) and stats[-1].get("output_tokens") is not None


def test_a_kept_reply_streams_its_thinking_before_its_words(ai_client, fake_ollama, session, fixed_clock):
    _seed(session)
    fake_ollama.librarian_thinking = "Three are waiting."
    fake_ollama.librarian_reply = "Three things are waiting, and call mum comes first."
    events, _answer = _stream(ai_client, "What is due?", True)
    kinds = [e["type"] for e in events if e["type"] in ("thinking", "answer")]
    assert kinds[0] == "thinking" and "answer" in kinds


def test_a_count_that_drops_the_figure_is_refused(ai_client, fake_ollama, session, fixed_clock):
    _seed(session, reminders=False)
    fake_ollama.librarian_reply = "You have a lovely notebook."
    events, answer = _stream(ai_client, "How many notes do I have?", False)
    assert "lovely" not in answer and "3" in answer
    assert _last_meta(events)["answered_by"] is None


@pytest.mark.parametrize("question", ["What is due?", "How many notes do I have?", "what is 12 * 7"])
@SURFACES
def test_with_no_model_the_engine_still_answers(client, session, fixed_clock, question, use_tools):
    _seed(session)
    events, answer = _stream(client, question, use_tools)
    assert answer.strip()
    assert _last_meta(events)["answered_by"] is None
    if question == "What is due?":
        for text, _due in DUE:
            assert text in answer
    elif question.startswith("How many"):
        assert "3 notes" in answer
    else:
        assert "84" in answer


#: The engine's facts for three reminders, one of them on "Mon 2 Nov": a 2
#: in a date is no count, so it cannot excuse "two reminders" (the review of
#: 2026-10-27 measured "two", "one", "no", "10" and "30 reminders" passing).
REMINDER_FACTS = "You have 3 reminders waiting.\n\n| call mum | Mon 2 Nov, 9:00 | #/notes/12 |\n| pay rent | Thu 5 Nov, 10:00 |\n| book dentist | Fri 30 Oct, 11:00 |"
REMINDER_COUNTS = {"reminder": {"3"}}


@pytest.mark.parametrize(
    ("prose", "ok"),
    [
        ("Three things are waiting; call mum is first.", True),
        ("You have 3 reminders, the first on Monday 2 November at 9:00.", True),
        ("One of them, call mum, is on Mon 2 Nov.", True),
        ("You have two reminders.", False),
        ("You have one reminder.", False),
        ("You have no reminders right now.", False),
        ("You have 10 reminders.", False),
        ("You have 30 reminders.", False),
        ("You have 4 reminders.", False),
        ("Two are waiting, starting Mon 2 Nov.", False),
        ("Nothing is due.", False),
        ("You have 3 notes waiting.", False),
        ("You have 12 reminders.", False),
    ],
)
def test_the_fact_check(prose: str, ok: bool) -> None:
    from tessellate.ai import fact_check

    assert fact_check.keeps(prose, REMINDER_FACTS, "What is due?", REMINDER_COUNTS, needs_figure=False) is ok


@pytest.mark.parametrize(
    ("prose", "ok"),
    [("That comes to 84.", True), ("That comes to 85.", False), ("Twelve sevens.", False), ("It is 84 at 14:02.", True)],
)
def test_the_fact_check_of_a_worked_sum(prose: str, ok: bool) -> None:
    """A sum counts nothing: every figure is one the facts or the question
    state, and the result must be said; a time is still no figure."""
    from tessellate.ai import fact_check

    assert fact_check.keeps(prose, "12 × 7 = 84", "what is 12 * 7", {}, needs_figure=True) is ok


def test_the_counts_come_from_the_result_not_from_dates() -> None:
    from tessellate.ai import fact_check

    result = {"reminders": [{"id": 1}, {"id": 2}, {"id": 3}], "total": 3, "offset": 0, "label": "Due"}
    assert fact_check.result_counts("list_reminders", result) == {"reminder": {"3"}}
    assert fact_check.said_counts("You have 3 reminders, due Mon 2 Nov at 14:02.") == {"reminder": {"3"}}
    stats = {"kind": "tag-count", "facts": [{"label": "tags", "count": 4}]}
    assert fact_check.rows_counts(stats) == {"tag": {"4"}}


#: 14:02 on the same Tuesday: a 2 in the clock is no count either.
AT_14_02 = datetime(2026, 10, 27, 14, 2)


@pytest.mark.parametrize("prose", ["You have two reminders.", "You have 2 reminders, the next at 14:02."])
def test_a_2_in_the_clock_does_not_excuse_two_reminders(ai_client, fake_ollama, session, monkeypatch, prose):
    monkeypatch.setattr(routes_chat, "user_now", lambda _config=None: AT_14_02)
    _seed(session)
    fake_ollama.librarian_reply = prose
    events, answer = _stream(ai_client, "What is due?", True)
    assert fake_ollama.chat_calls
    assert prose not in answer
    assert _last_meta(events)["answered_by"] is None


#: Which sentences ask for a change, not a figure (`_asks_change`): the review
#: of 2026-10-27 found double lead-ins missed and "update me on", "complete
#: list of" and "add up" taken for changes.
CHANGE_CASES = [
    ("save my first note", True),
    ("can you please save my first note", True),
    ("please, could you tag my first note work", True),
    ("hey can you delete the gym note", True),
    ("remind me to call mum at 5", True),
    ("add a tag to the gym note", True),
    ("update the gym note", True),
    ("complete the dentist reminder", True),
    ("update me on what is due", False),
    ("complete list of my tags", False),
    ("add up my expenses", False),
    ("add up 12, 30 and 5", False),
    ("add 3 and 4", False),
    ("what is due", False),
    ("how many notes do I have", False),
    ("addresses in my notes", False),
    ("settings for reminders", False),
]


@pytest.mark.parametrize(("question", "change"), CHANGE_CASES)
def test_which_sentences_ask_for_a_change(question: str, change: bool) -> None:
    assert routes_chat._asks_change(question) is change


def _facts_prompted(fake) -> bool:
    from tessellate.ai import librarian

    return any(librarian.FACTS_BRIEF[:60] in str(m.get("content") or "") for call in fake.chat_calls for m in call)


@SURFACES
def test_a_change_with_a_count_in_it_is_never_a_facts_turn(ai_client, fake_ollama, session, fixed_clock, use_tools):
    """"can you please save my first note" read as the first-note statistic:
    the model was handed the first note's date to say (the review measured
    it on both surfaces)."""
    _seed(session, reminders=False)
    fake_ollama.librarian_reply = "Your first note is from today."
    _stream(ai_client, "can you please save my first note", use_tools)
    assert not _facts_prompted(fake_ollama)


@SURFACES
def test_add_up_takes_the_facts_path_with_its_calculator(ai_client, fake_ollama, session, fixed_clock, use_tools):
    """"add up" asks for a sum: the model says it from the worked total and the
    calculator still rides under it ("add" alone was read as a change, so the
    popup agent lost both)."""
    fake_ollama.librarian_reply = "Those come to 47."
    events, answer = _stream(ai_client, "add up 12, 30 and 5", use_tools)
    assert _facts_prompted(fake_ollama) and "47" in _prompt(fake_ollama)
    assert answer == "Those come to 47."
    assert _last_meta(events)["answered_by"]
    assert [e["panel"] for e in events if e["type"] == "panel"] == ["calculator"]


def _seed_filed(session) -> None:
    from tessellate.core.database import Category

    cats = [Category(name=n) for n in ("Work", "Home", "Health", "Uni")]
    session.add_all(cats)
    session.commit()
    for i in range(12):
        session.add(Entry(content=f"Note number {i} about things", category_id=cats[i % 4].id, tags=json.dumps(["work"] if i % 2 else ["home", "gym"])))
    session.commit()


@pytest.mark.parametrize(
    ("question", "rows"),
    [("how many notes in each category", ("Work", "Home", "Health", "Uni")), ("which tags do I use most", ("home", "gym", "work"))],
)
@SURFACES
def test_a_counted_list_keeps_its_rows_under_the_models_words(ai_client, fake_ollama, session, fixed_clock, question, rows, use_tools):
    """The statistic was one answer, so the model's one line replaced the
    whole list ("Each one holds 3 notes.", the review of 2026-10-27), while
    the brief promises the list is shown under it."""
    _seed_filed(session)
    fake_ollama.librarian_reply = "Each one holds 3 notes." if "category" in question else "Three tags share the top spot."
    events, answer = _stream(ai_client, question, use_tools)
    assert answer.startswith(fake_ollama.librarian_reply), answer
    for label in rows:
        assert f"{label} (" in answer, (label, answer)
    assert _last_meta(events)["answered_by"]


@SURFACES
def test_a_read_said_as_an_act_is_written_by_the_model(ai_client, fake_ollama, session, fixed_clock, use_tools):
    """"list my work notes" in Ask mode reads as an act (`intent.ACT`), so the
    composer answered it with the model up (the review of 2026-10-27): a read
    is facts like any other, and its list rides under the model's words."""
    _seed_filed(session)
    fake_ollama.librarian_reply = "Three Work notes, newest first."
    events, answer = _stream(ai_client, "list my work notes", use_tools)
    assert _facts_prompted(fake_ollama)
    assert answer.startswith(fake_ollama.librarian_reply) and "#/notes/" in answer, answer
    assert _last_meta(events)["answered_by"]


def test_a_read_said_as_an_act_is_the_engines_with_no_model(client, session, fixed_clock) -> None:
    _seed_filed(session)
    events, answer = _stream(client, "list my work notes", False)
    assert answer.startswith("Here are your three Work notes") and _last_meta(events)["answered_by"] is None


def test_which_statistics_are_lists() -> None:
    boards = {"kind": "boards", "text": "You have 2 boards, last changed first:\n- [Plan](#/board/1)\n- [Trip](#/board/2)", "facts": []}
    assert routes_chat._stats_listed(boards) == [{"type": "answer", "delta": "\n\n- [Plan](#/board/1)\n- [Trip](#/board/2)"}]
    worked = {"kind": "utility", "text": "The total of 12, 30, 5 is 47.\nRead as the sum of 3 numbers.", "facts": []}
    untagged = {"kind": "untagged", "text": "2 notes out of 5 have no tags.", "facts": [{"label": "untagged", "count": 2}, {"label": "total", "count": 5}]}
    assert routes_chat._stats_listed(worked) == routes_chat._stats_listed(untagged) == []


def test_the_counted_list_is_one_line_with_no_model(client, session, fixed_clock) -> None:
    _seed_filed(session)
    _events, answer = _stream(client, "how many notes in each category", False)
    assert answer.startswith("Notes per category: ") and "\n" not in answer


def test_the_facts_prompt_is_budgeted() -> None:
    """Prompt text is budgeted (CLAUDE.md section 7): the brief is one short
    paragraph, and the facts are cut to a fixed size however long the list."""
    from tessellate.ai import librarian

    assert len(librarian.FACTS_BRIEF) <= 400
    messages = librarian.build_facts_messages("What is due?", "row\n" * 5000)
    assert len(messages[-1]["content"]) <= librarian.FACTS_MAX_CHARS + 300


def test_the_guide_says_who_writes_a_counted_answer() -> None:
    """Help moves with the behaviour (standing order 13)."""
    from tessellate.ai import help_chat

    topics = {t["id"]: t["body"] for t in help_chat.HELP_TOPICS}
    assert "says the counted answer in its own words" in topics["notebook-questions"]
