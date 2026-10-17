"""Slash commands (O6; BACKLOG "Slash commands in Chat and the composer" and
"Composer: natural language equals slash commands"). One registry
(`ai/slash.py`) feeds the route, `GET /chat/commands`, `/help` and the "/"
menu's Commands row; every command answers with no model. Before: "/recent
3" in Chat answered "I couldn't find any saved notes matching that
question" (measured on :8785, 2026-10-17)."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from tessellate.ai import help_chat, reading, slash
from tessellate.core.database import Reminder
from tessellate.entry import manager

ROOT = Path(__file__).resolve().parents[1]
READER = reading.__name__


def _say(client, question: str, **body) -> str:
    text = []
    with client.stream("POST", "/chat/stream", json={"question": question, **body}) as response:
        for line in response.iter_lines():
            if line.strip():
                event = json.loads(line)
                if event.get("type") == "answer":
                    text.append(event["delta"])
    return "".join(text)


@pytest.fixture()
def notebook(session):
    manager.create_entry(session, "Golf after work, hit a bucket of balls", "Sport", ["golf"])
    manager.create_entry(session, "Golf lesson with the club pro", "Sport", ["golf"])
    manager.create_entry(session, "Dentist on Tuesday at 3pm")
    manager.create_entry(session, "Grocery list: milk and eggs")
    session.commit()
    return session


@pytest.mark.parametrize("body", [{"use_tools": True}, {"use_tools": False}, {"notes_only": True, "answer_from": "notes", "use_tools": False}])
def test_each_command_answers_exactly_in_chat_and_ask(client, notebook, body):
    assert _say(client, "/recent 2", **body).startswith("Your two newest notes:")
    assert "Grocery list" in _say(client, "/recent 2", **body)
    assert _say(client, "/count", **body) == "You have four notes."
    assert _say(client, "/count golf", **body) == "Two of your 4 notes are tagged #golf."
    assert _say(client, "/count sport", **body) == "Two of your 4 notes are in sport."
    assert _say(client, "/count dentist", **body) == "One of your 4 notes mentions “dentist”."
    made = _say(client, "/made today", **body)
    assert made.startswith("You wrote four notes today:") and "Golf lesson" in made, made
    assert "last month" in _say(client, "/made last month", **body)
    untagged = _say(client, "/untagged", **body)
    assert untagged.startswith("Two notes have no tags:") and "Dentist" in untagged and "Golf" not in untagged.split("\n\n")[1]


def test_help_lists_every_command_and_says_how_to_type_one(client, notebook):
    listed = _say(client, "/help")
    for command in slash.COMMANDS.values():
        assert command.usage in listed
    assert _say(client, "/help made").startswith("**/made [day or span]**")
    assert _say(client, "/frobnicate").startswith("There's no /frobnicate command.")
    assert "Try /made yesterday" in _say(client, "/made bananas")
    assert "Say when" in _say(client, "/made")


def test_a_typed_command_is_exact_with_a_model_running_too(ai_client, notebook):
    assert _say(ai_client, "/count golf", use_tools=True) == "Two of your 4 notes are tagged #golf."


def test_plain_words_run_the_command(client, notebook):
    said = _say(client, "which notes have no tags", use_tools=False)
    assert said.startswith("Two notes have no tags:"), said


def test_one_registry_feeds_the_route_the_menu_and_the_help(client):
    """The "/" menu has a row for every command, built from the route's list
    (O6 rest), not a copy of the names; /help and the Guide topic name each."""
    names = [c["name"] for c in client.get("/chat/commands").json()["commands"]]
    assert names == list(slash.COMMANDS)
    editor = (ROOT / "frontend" / "js" / "editor.js").read_text(encoding="utf-8")
    fn = editor[editor.index("function chatSlashRows"):].split("\n}\n", 1)[0]
    assert 'apiJson("/chat/commands")' in fn and 'id: `chat-cmd-${c.name}`' in fn and "label: c.usage" in fn
    assert "...chatSlashRows(afterPress)" in editor
    topic = next(t for t in help_chat.HELP_TOPICS if t["id"] == "slash-commands")
    for name in names:
        assert f"/{name}" in topic["body"], name
    assert 'sendChatMessage("/help")' in fn


def test_house_style():
    for text in [c.summary for c in slash.COMMANDS.values()]:
        assert "!" not in text and chr(0x2014) not in text and text[:1].islower()


# --- the rest of the registry (O6 rest) ----------------------------------------------------
#: Measured on a running app with no model before this: "/find golf" answered
#: "There's no /find command." and "/due" the same, for every name below.

NOW = datetime(2026, 10, 17, 10, 0)


@pytest.fixture()
def dated(session):
    made = [
        manager.create_entry(session, "# Golf\n\nNine holes with Sam.", "Sport", ["golf"]),
        manager.create_entry(session, "# Dentist\n\nCheck-up on Tuesday. Ask about the night guard.", tags=["health"]),
        manager.create_entry(session, "# Chores\n\n- [ ] call the plumber\n- [x] post the parcel\n- [ ] book the dentist"),
        manager.create_entry(session, "# Old idea\n\nA tent that folds itself."),
    ]
    for entry, day in zip(made, (17, 16, 10, 1), strict=True):
        entry.created_at = datetime(2026, 10, day, 9, 0)
    made[0].pinned = True
    session.add(Reminder(text="Book the boiler service", due_at=datetime(2026, 10, 17, 15, 0)))
    session.add(Reminder(text="Renew the passport", due_at=datetime(2026, 10, 15, 9, 0)))
    session.add(Reminder(text="Dentist follow-up", due_at=datetime(2026, 10, 20, 9, 0)))
    session.add(Reminder(text="Already done", due_at=datetime(2026, 10, 17, 8, 0), done=True))
    session.commit()
    return made


def _run(session, text):
    return slash.answer(session, text, NOW, typed_only=True)


def test_today_and_yesterday_are_made_for_that_day(session, dated):
    assert _run(session, "/today").startswith("You wrote one note today:") and "Golf" in _run(session, "/today")
    assert "Dentist" in _run(session, "/yesterday") and "Golf" not in _run(session, "/yesterday")


def test_find_wants_every_word(session, dated):
    assert _run(session, "/find dentist tuesday").startswith("One note mentions “dentist tuesday”:")
    assert "Dentist" in _run(session, "/find dentist")
    assert _run(session, "/find dentist golf") == "No note holds both “dentist golf”."
    assert _run(session, "/find").startswith("Say what to find")


def test_pinned_oldest_random(session, dated):
    pinned = _run(session, "/pinned")
    assert pinned.startswith("One note is pinned:") and "Golf" in pinned
    assert _run(session, "/oldest 1").startswith("Your oldest note:") and "Old idea" in _run(session, "/oldest 1")
    assert _run(session, "/oldest 2").startswith("Your two oldest notes:")
    assert _run(session, "/random").startswith("Here is one of your 4 notes, picked at random:")


def test_tags_and_categories_count(session, dated):
    assert _run(session, "/tags") == "You use two tags, most used first: #golf (1), #health (1)."
    said = _run(session, "/categories")
    assert said.startswith("Your notes sit in ") and "Sport (1)" in said and "(3)" in said


def test_todo_lists_open_boxes_only(session, dated):
    said = _run(session, "/todo")
    assert said.startswith("Two open checkboxes:") and "call the plumber" in said and "book the dentist" in said
    assert "post the parcel" not in said


def test_due_lists_today_and_overdue_then_the_week(session, dated):
    today = _run(session, "/due")
    assert today.startswith("Two reminders are due today or overdue:")
    assert "Renew the passport (overdue since 15 October)" in today and "Book the boiler service (Saturday 17 October, 15:00)" in today
    assert "Already done" not in today and "follow-up" not in today
    assert _run(session, "/due week").startswith("Three reminders are due this week or overdue:")


def test_calc_is_exact_and_refuses_what_is_not_a_sum(session):
    assert _run(session, "/calc 15 * 80 / 100") == "15 * 80 / 100 = 12"
    assert _run(session, "/calc 0.1 + 0.2") == "0.1 + 0.2 = 0.3"
    assert _run(session, "/calc __import__('os')").startswith("I can only work out sums")
    assert _run(session, "/calc").startswith("Give me a sum")


def test_stats_and_orphans(session, dated):
    from tessellate.core.database import EntryLink

    stats = _run(session, "/stats")
    assert stats.startswith("You have four notes and ") and "Your newest note is from 17 October 2026" in stats
    assert "written on four days" in stats
    assert _run(session, "/orphans").startswith("Four notes link to nothing:")
    session.add(EntryLink(source_entry_id=dated[0].id, target_entry_id=dated[1].id))
    session.commit()
    assert _run(session, "/orphans").startswith("Two notes link to nothing:")


def test_an_empty_notebook_says_so(session):
    for name in ("/stats", "/oldest", "/random", "/categories"):
        assert _run(session, name) == "You have no notes yet.", name
    assert _run(session, "/tags") == "No note has a tag yet."
    assert _run(session, "/pinned").startswith("No note is pinned.")
    assert _run(session, "/todo") == "No note has an open checkbox."
    assert _run(session, "/due") == "No reminder is due today or overdue."


def test_every_command_has_a_usage_example_and_help_row():
    for command in slash.COMMANDS.values():
        assert command.usage.startswith(f"/{command.name}") and command.example.startswith(f"/{command.name}")
        assert command.summary.endswith(".") and chr(0x2014) not in command.summary


# --- natural language equals the command (O6 rest) ------------------------------------------
#: Measured on :8795 with no model before: "what are my pinned notes" answered
#: "Nothing comes up for “pinned”", "do I have any open todos" "I couldn't find
#: anything on “open” or “todos”", "give me a random note" "Nothing I found
#: mentions “give” or “random”"; "show my oldest notes" was called an act.


@pytest.mark.parametrize(
    ("said", "read"),
    [
        ("what are my pinned notes", ("pinned", "")),
        ("which notes are pinned?", ("pinned", "")),
        ("show me my pinned notes", ("pinned", "")),
        ("show my oldest notes", ("oldest", "")),
        ("what are my 3 oldest notes", ("oldest", "3")),
        ("list the oldest notes I have", ("oldest", "")),
        ("do I have any open todos", ("todo", "")),
        ("show my unchecked checkboxes", ("todo", "")),
        ("which notes have open to-dos", ("todo", "")),
        ("give me a random note", ("random", "")),
        ("show me a random note", ("random", "")),
        ("pick a random note for me", ("random", "")),
        ("which notes have no tags", ("untagged", "")),
        #: The owner's slips are fixtures: the speller puts them right first.
        ("wich notes are pined", ("pinned", "")),
        ("shwo my oldst notes", ("oldest", "")),
        ("give me a rendom note", ("random", "")),
        ("do i have any opne todos", ("todo", "")),
    ],
)
def test_plain_words_read_as_the_command(said, read):
    assert slash.infer(said) == read


@pytest.mark.parametrize(
    "said",
    [
        "pin the dentist note",
        "what did I decide about the pinned cable",
        "my oldest friend is called Sam",
        "remind me to check the todo list",
        "what is a random walk",
        "I need an open space for the party",
        "hello",
    ],
)
def test_other_sentences_are_not_commands(said):
    assert slash.infer(said) is None
