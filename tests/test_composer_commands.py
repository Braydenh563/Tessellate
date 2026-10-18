"""The acts: commands read from a Chat message with no model (CHAT_PLAN
Phase 6 step 7, decision 38; Phase 5 (f)).

`ai/commands.read` turns a sentence into an intent and its arguments with
rules, no model. The table below is the measurement the plan asks for: each
row is a phrasing, the intent it should read as, and the arguments it should
carry; `test_the_table_accuracy` reports the share read exactly, and every
row is also its own test so a regression names its sentence.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from tessellate.ai import commands

#: Tuesday 6 October 2026, 10:00 at UTC+10.
NOW = datetime(2026, 10, 6, 10, 0, tzinfo=timezone(timedelta(hours=10)))


def _at(day: int, hour: int, minute: int = 0) -> str:
    return datetime(2026, 10, day, hour, minute, tzinfo=NOW.tzinfo).strftime("%Y-%m-%d %H:%M")


#: (phrasing, intent or None, the arguments that must match)
TABLE: list[tuple[str, str | None, dict]] = [
    # Reminders: the time read by `ai/when`, the words left as the reminder.
    ("remind me to call mum on Friday", "reminder", {"text": "Call mum", "due": _at(9, 9)}),
    ("Remind me to renew my passport tomorrow at 5pm", "reminder", {"text": "Renew my passport", "due": _at(7, 17)}),
    ("remind me in 20 minutes to check the oven", "reminder", {"text": "Check the oven", "due": _at(6, 10, 20)}),
    ("set a reminder to pay rent next Monday", "reminder", {"text": "Pay rent", "due": _at(12, 9)}),
    ("make a reminder for the dentist on Friday at 3pm", "reminder", {"text": "The dentist", "due": _at(9, 15)}),
    ("add a reminder: water the plants tonight", "reminder", {"text": "Water the plants", "due": _at(6, 20)}),
    ("remind me about the passport renewal tomorrow morning", "reminder", {"text": "The passport renewal", "due": _at(7, 9)}),
    ("please remind me to email Priya", "reminder", {"text": "Email Priya", "due": _at(7, 9), "time_given": False}),
    ("can you remind me to book flights on 14 October?", "reminder", {"text": "Book flights", "due": _at(14, 9)}),
    ("reminder: submit the tax return in 3 days", "reminder", {"text": "Submit the tax return", "due": _at(9, 10)}),
    ("set a reminder for Friday to collect the parcel", "reminder", {"text": "Collect the parcel", "due": _at(9, 9)}),
    ("remind me what I wrote about Friday", None, {}),
    ("remind me about my trip", None, {}),
    ("what reminders do I have tomorrow?", None, {}),
    # Tags: "these" is the notes attached to the message; "about Z" is a search.
    ("tag these notes trip", "tag", {"these": True, "tags": ["trip"]}),
    ("tag my notes about Japan with travel", "tag", {"about": "Japan", "tags": ["travel"]}),
    ("tag notes about the kitchen renovation as #home", "tag", {"about": "kitchen renovation", "tags": ["home"]}),
    ("add the tag urgent to this note", "tag", {"these": True, "tags": ["urgent"]}),
    ("tag everything about Priya with work, followup", "tag", {"about": "Priya", "tags": ["work", "followup"]}),
    ("label these #trip #japan", "tag", {"these": True, "tags": ["trip", "japan"]}),
    ("tag the note about the plumber with home", "tag", {"about": "plumber", "single": True, "tags": ["home"]}),
    ("can you tag my japan notes with travel please", "tag", {"about": "japan", "tags": ["travel"]}),
    # Moves: a category by name, matched to an existing one when it plans.
    ("move these notes to Work", "move", {"these": True, "category": "Work"}),
    ("move my notes about the plumber to Home", "move", {"about": "plumber", "category": "Home"}),
    ("file the note about taxes under Finance", "move", {"about": "taxes", "single": True, "category": "Finance"}),
    ("put this note in Projects", "move", {"these": True, "category": "Projects"}),
    ("move my recipe notes into the Cooking category", "move", {"about": "recipe", "category": "Cooking"}),
    ("move the meeting to Friday", None, {}),
    # New notes: the words after the verb, as said.
    ("note: buy milk and eggs", "new_note", {"content": "Buy milk and eggs"}),
    ("new note: Ideas for the garden", "new_note", {"content": "Ideas for the garden"}),
    ("make a note that the boiler code is 4471", "new_note", {"content": "The boiler code is 4471"}),
    ("jot down call the bank about the card", "new_note", {"content": "Call the bank about the card"}),
    ("save a note saying Priya prefers Thursdays", "new_note", {"content": "Priya prefers Thursdays"}),
    ("take a note: flight lands at 6am", "new_note", {"content": "Flight lands at 6am"}),
    ("note to self: renew the car insurance", "new_note", {"content": "Renew the car insurance"}),
    # Find and open: read only, nothing to confirm.
    ("find my note about the passport", "find", {"about": "passport"}),
    ("show me my notes about Japan", "find", {"about": "Japan"}),
    ("search for tax receipts", "find", {"about": "tax receipts"}),
    ("where is my wifi password note?", "find", {"about": "wifi password"}),
    ("look up notes on gardening", "find", {"about": "gardening"}),
    ("open the note about the boiler", "open", {"about": "boiler"}),
    ("open my passport note", "open", {"about": "passport"}),
    ("open note 12", "open", {"note_id": 12}),
    ("find out why my tests fail", None, {}),
    # Meetings: a title when one is said.
    ("start a meeting", "meeting", {"title": ""}),
    ("start a meeting about the budget", "meeting", {"title": "Budget"}),
    ("begin a new meeting called Weekly sync", "meeting", {"title": "Weekly sync"}),
    ("start the weekly sync meeting", "meeting", {"title": "Weekly sync"}),
    ("let's start a meeting with Priya", "meeting", {"title": "Meeting with Priya"}),
    ("record a meeting", "meeting", {"title": ""}),
    # Phase 6: the rest of the grammar (decision 38).
    ("delete the boiler note", "delete", {"about": "boiler", "single": True}),
    ("please delete my passport note", "delete", {"about": "passport", "single": True}),
    ("bin this note", "delete", {"these": True}),
    ("pin the dentist note", "pin", {"about": "dentist", "single": True}),
    ("unpin the dentist note", "unpin", {"about": "dentist", "single": True}),
    ("untag the gym note from training", None, {}),
    ("remove the tag urgent from this note", "untag", {"these": True, "tags": ["urgent"]}),
    ("link the gym note to the running note", "link", {"about": "gym", "other": "running"}),
    ("unlink the gym note from the running note", "unlink", {"about": "gym", "other": "running"}),
    ("rename the gym note to Strength plan", "rename", {"about": "gym", "title": "Strength plan"}),
    ("add buy chalk to the gym note", "append", {"about": "gym", "content": "Buy chalk"}),
    ("summarise my gym notes", "summarise", {"about": "gym"}),
    ("open settings", "navigate", {"surface": "settings"}),
    ("go to the graph", "navigate", {"surface": "graph"}),
    # Decision 42: archiving stays a UI action.
    ("archive the gym note", None, {}),
    # Look-alikes: questions about acts, never acts.
    ("how do I delete a note?", None, {}),
    ("did I pin the dentist note?", None, {}),
    ("can I rename a tag?", None, {}),
    ("should I link these notes", None, {}),
    ("delete the tag urgent", None, {}),
    # Not commands: questions and chat go to the composer as before.
    ("what did I write about Japan?", None, {}),
    ("how many notes do I have", None, {}),
    ("hello", None, {}),
    ("move on", None, {}),
    ("I need to call mum tomorrow", None, {}),
    ("can you tag notes?", None, {}),
]


def _read(phrase: str) -> dict | None:
    parsed = commands.read(phrase, NOW)
    if parsed is None:
        return None
    out = dict(parsed)
    if "due_at" in out:
        out["due"] = out.pop("due_at").strftime("%Y-%m-%d %H:%M")
    return out


def _matches(phrase: str, intent: str | None, want: dict) -> bool:
    got = _read(phrase)
    if intent is None:
        return got is None
    return got is not None and got["intent"] == intent and all(got.get(k) == v for k, v in want.items())


@pytest.mark.parametrize(("phrase", "intent", "want"), TABLE, ids=[row[0] for row in TABLE])
def test_each_phrasing(phrase, intent, want):
    got = _read(phrase)
    if intent is None:
        assert got is None, got
        return
    assert got is not None, phrase
    assert got["intent"] == intent, got
    for key, value in want.items():
        assert got.get(key) == value, (key, got)


def test_the_table_accuracy():
    """At least 40 phrasings, every one read exactly (the measured number)."""
    assert len(TABLE) >= 40
    right = sum(_matches(*row) for row in TABLE)
    assert right == len(TABLE), f"{right} of {len(TABLE)}"


def test_every_write_intent_is_in_the_capability_line():
    line = commands.CAPABILITY_LINE
    for words in ("set a reminder", "tag notes", "move notes", "make a new note", "find or open a note", "start a meeting"):
        assert words in line
    assert chr(0x2014) not in line and "!" not in line


# Task requests reach their act with no model, in people's words and the
# owner's typos (the composer ledger's "tasks and routing, 30 gold"). The gold
# is `fixtures/composer/tasks_1011.json`: before `commands.read_typed`, 18 of
# 30 reached their act as typed; after, 30 of 30, and no control writes.

TASKS_GOLD = json.loads((Path(__file__).parent / "fixtures" / "composer" / "tasks_1011.json").read_text(encoding="utf-8"))
TASKS_NOW = datetime.fromisoformat(TASKS_GOLD["now"])
#: Measured 2026-10-11: 18 of 30 before, 30 of 30 after.
TASKS_FLOOR = 1.0


def _intent(typed: str) -> str | None:
    found = commands.read_typed(typed, TASKS_NOW)
    return found["intent"] if found else None


def test_the_gold_tasks_reach_their_act():
    misses = [(typed, want, _intent(typed)) for typed, want in TASKS_GOLD["tasks"] if _intent(typed) != want]
    assert len(TASKS_GOLD["tasks"]) >= 30
    assert 1 - len(misses) / len(TASKS_GOLD["tasks"]) >= TASKS_FLOOR, misses


def test_a_question_that_looks_like_a_task_writes_nothing():
    wrong = [(typed, _intent(typed)) for typed in TASKS_GOLD["not_acts"] if _intent(typed) in commands.WRITE_INTENTS]
    assert not wrong, wrong


def test_the_reminder_says_what_was_typed_put_right():
    found = commands.read_typed("pls remind me 2 buy milk tonight", TASKS_NOW)
    assert found["said"] == "buy milk" and found["time_given"]
    found = commands.read_typed("remind me to call mum tmrw", TASKS_NOW)
    assert found["said"] == "call mum" and found["due_at"].date().isoformat() == "2026-10-12"


def test_a_tag_said_after_the_note_tags_that_note():
    assert commands.read("tag the dentist note health", TASKS_NOW) == {"intent": "tag", "about": "dentist", "single": True, "tags": ["health"]}


def test_through_the_route_a_typed_task_is_an_act(client, session):
    from tessellate.entry import manager

    manager.create_entry(session, "# Old wifi\n\nPassword 1234.")
    session.commit()
    with client.stream("POST", "/chat/stream", json={"question": "delte my old wifi note", "use_tools": True}) as response:
        events = [json.loads(line) for line in response.iter_lines() if line.strip()]
    assert any(e["type"] == "act" for e in events), events


def _stream(client, question: str, history: list | None = None) -> list[dict]:
    body = {"question": question, "use_tools": True, "history": history or []}
    with client.stream("POST", "/chat/stream", json=body) as response:
        return [json.loads(line) for line in response.iter_lines() if line.strip()]


def test_a_reminder_with_no_time_is_asked_once_and_the_answer_sets_it(client, session, monkeypatch):
    """OPEN-ledger row 461 (decisions 48 and 50): no time said is asked,
    never guessed as tomorrow at 9; the next turn's time fills it."""
    from tessellate.api import routes_chat
    from tessellate.core.database import Reminder

    monkeypatch.setattr("tessellate.core.config.user_now", lambda _config: TASKS_NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _config: TASKS_NOW)

    asked = _stream(client, "remind me to call the dentist")
    text = "".join(e.get("delta", "") for e in asked if e["type"] == "answer")
    assert "call the dentist" in text and text.rstrip().endswith("?"), text
    assert not any(e["type"] == "act" for e in asked) and session.query(Reminder).count() == 0
    history = [{"question": "remind me to call the dentist", "answer": text}]
    done = _stream(client, "friday at 3", history)
    card = next(e for e in done if e["type"] == "act")
    assert card["label"].startswith("Remind you on Friday at 3") and card["label"].endswith("call the dentist"), card


def test_a_time_alone_fills_only_a_reminder_left_waiting():
    from tessellate.ai import reading

    turns = [{"text": "remind me to call the dentist", "objects": []}]
    assert reading.follow("friday at 3", turns, TASKS_NOW) == ("remind me to call the dentist friday at 3", "slot")
    assert reading.follow("tmrw", turns, TASKS_NOW)[1] == "slot"
    assert reading.follow("friday at 3", [{"text": "remind me to call the dentist at 5pm", "objects": []}], TASKS_NOW) is None
    assert reading.follow("friday at 3 call Sam", turns, TASKS_NOW) is None


def test_a_reminder_time_says_which_half_of_the_day():
    """The chips probe, 2026-10-11: 00:39 and 12:39 both read "12:39"."""
    from tessellate.ai.commands import _clock

    said = [_clock(datetime(2026, 1, 1, h, m)) for h, m in ((0, 0), (0, 39), (12, 0), (12, 39), (9, 0), (17, 30), (5, 0))]
    assert said == ["midnight", "12:39am", "noon", "12:39pm", "9", "5:30pm", "5am"]


def test_tonight_said_late_is_still_tonight_and_a_time_gone_is_asked():
    """The chips probe: "tonight" after eight was eight o'clock gone by, and
    the store refused it ("Nothing was changed")."""
    from tessellate.ai import reading

    late = datetime(2026, 10, 11, 21, 40, tzinfo=timezone.utc)
    tonight = commands.read_typed("remind me to call mum tonight", late)
    assert tonight["due_at"] == datetime(2026, 10, 11, 22, 0, tzinfo=timezone.utc) and tonight["time_given"]
    gone = commands.read_typed("remind me to call mum tonight at 8", late)
    assert not gone["time_given"]
    filled = reading.follow("10pm", [{"text": "remind me to call mum tonight at 8", "objects": []}], late)
    assert filled == ("remind me to call mum 10pm", "slot")


def test_a_note_filed_under_a_word_that_is_also_a_nickname_is_moved(client, session):
    """The chips probe: "sport" at the end was taken for a nickname ("thanks
    sport"), so "file the golf note under sport" lost its category and was
    answered from the notes."""
    from tessellate.entry import manager

    manager.create_entry(session, "# Golf\n\nTee time Saturday with Sam.")
    session.commit()
    card = next(e for e in _stream(client, "file the golf note under sport") if e["type"] == "act")
    assert "sport" in card["label"].lower(), card


def test_the_running_model_manager_is_never_its_module():
    """The Chromium after-run, 2026-10-11: deps imported the model manager
    module as `_model_manager`, the running manager's own name, so a real
    server answered every chat and /models/status with a 500."""
    import os
    import subprocess
    import sys
    from pathlib import Path

    code = "import types; from tessellate.core import deps; print(isinstance(deps._model_manager, types.ModuleType))"
    #: pytest.ini's `pythonpath = src` reaches this process, not a child's
    #: environment: under `gate.sh` (no PYTHONPATH exported) the child could not
    #: import `tessellate` and the test failed there only.
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
    ran = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True, timeout=120, env=env)
    assert ran.stdout.strip() == "False", ran.stdout + ran.stderr
