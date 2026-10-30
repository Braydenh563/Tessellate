"""Composer audit 1028 row E10: tasks as acts, with no model. A task is a
reminder (decision 75: the reminders are the app's task list) or an unticked
checklist line in a note. "add a task to read chapter 5 tomorrow" sets a
reminder; "tick off buy milk" completes the one reminder or checklist line it
names, and asks when it could be more than one. Each is tested over several
phrasings, including ones the reader was not designed around (INBOX 1357).
Fixed clock: Wednesday 28 October 2026, 10:00."""

from __future__ import annotations

import datetime as dt
import json

import pytest

from tessellate.ai import acts, commands
from tessellate.api import routes_chat
from tessellate.core import config
from tessellate.core.database import Reminder
from tessellate.entry import manager

NOW = dt.datetime(2026, 10, 28, 10, 0, 0)
TOMORROW_9 = dt.datetime(2026, 10, 29, 9, 0)
FRIDAY_9 = dt.datetime(2026, 10, 30, 9, 0)

ADD_WITH_TIME = [
    ("add a task to read chapter 5 tomorrow", "Read chapter 5", TOMORROW_9),
    ("add a task: read chapter 5 tomorrow", "Read chapter 5", TOMORROW_9),
    ("add task read chapter 5 tomorrow", "Read chapter 5", TOMORROW_9),
    ("add chapter 5 reading to my to-do list tomorrow", "Chapter 5 reading", TOMORROW_9),
    ("add chapter 5 reading to my to do list for tomorrow", "Chapter 5 reading", TOMORROW_9),
    ("put buy milk on my todo list for Friday", "Buy milk", FRIDAY_9),
    ("new task: call the bank on Friday", "Call the bank", FRIDAY_9),
    ("create a to-do to email Priya on Friday", "Email Priya", FRIDAY_9),
    ("add 'practice past paper' to my tasks for tomorrow", "Practice past paper", TOMORROW_9),
    ("can you please add a task to pay rent on Friday", "Pay rent", FRIDAY_9),
    ("Add a todo: water the plants tomorrow", "Water the plants", TOMORROW_9),
    ("add pay rent to my task list on friday", "Pay rent", FRIDAY_9),
]


@pytest.mark.parametrize(("sentence", "text", "due"), ADD_WITH_TIME)
def test_adding_a_task_reads_as_a_reminder_with_the_words_and_the_time(sentence, text, due):
    got = commands.read(sentence, NOW)
    assert got and got["intent"] == "reminder", got
    assert got["text"] == text and got["due_at"] == due and got["time_given"], got
    assert got["task"] is True


ADD_NO_TIME = [
    "add chapter 5 reading to my to-do list",
    "add a task to read chapter 5",
    "new task: buy milk",
    "put buy milk on my todo list",
]


@pytest.mark.parametrize("sentence", ADD_NO_TIME)
def test_a_task_with_no_time_is_read_so_it_can_be_asked_once(sentence):
    got = commands.read(sentence, NOW)
    assert got and got["intent"] == "reminder" and got["task"] and not got["time_given"], got


NOT_ADDING = [
    ("add buy chalk to the gym note", "append"),
    ("add a note: buy milk", "new_note"),
    ("add a reminder: water the plants tonight", "reminder"),
    ("what tasks do I have", None),
    ("how do I add a task?", None),
    ("is the task list sorted by date?", None),
    ("what is on my to-do list", None),
]


@pytest.mark.parametrize(("sentence", "intent"), NOT_ADDING)
def test_other_sentences_keep_their_own_reading(sentence, intent):
    got = commands.read(sentence, NOW)
    assert (got or {}).get("intent") == intent, got
    assert not (got or {}).get("task")


COMPLETE = [
    ("mark read chapter 5 as done", "read chapter 5", None),
    ("mark read chapter 5 done", "read chapter 5", None),
    ("mark off read chapter 5", "read chapter 5", None),
    ("tick off buy milk", "buy milk", None),
    ("tick buy milk off", "buy milk", None),
    ("please tick off the buy milk task", "buy milk", None),
    ("check off buy milk", "buy milk", None),
    ("cross off buy milk", "buy milk", None),
    ("cross buy milk off my list", "buy milk", None),
    ("complete the dentist reminder", "dentist", "reminder"),
    ("complete buy milk", "buy milk", None),
    ("mark the dentist task as complete", "dentist", None),
    ("mark the problem set 6 reminder as finished", "problem set 6", "reminder"),
    ("set buy milk as done", "buy milk", None),
    ("mark my dentist reminder as done", "dentist", "reminder"),
    ("tick off the hobsbawm checklist item", "hobsbawm", "checklist"),
]


@pytest.mark.parametrize(("sentence", "about", "kind"), COMPLETE)
def test_completing_a_task_names_it_in_the_persons_words(sentence, about, kind):
    got = commands.read(sentence, NOW)
    assert got and got["intent"] == "complete", got
    assert got["about"] == about and got.get("kind") == kind, got


NOT_COMPLETING = [
    "mark the calendar",
    "check the dentist note",
    "tick off",
    "what did I complete last week?",
    "is the dentist reminder done?",
    "remind me to tick off the list on Friday",
]


@pytest.mark.parametrize("sentence", NOT_COMPLETING)
def test_sentences_that_are_not_a_completion_are_left_alone(sentence):
    got = commands.read(sentence, NOW)
    assert (got or {}).get("intent") != "complete", got


# --- plan, run, undo -------------------------------------------------------------------------


def _reminder(session, text: str, *, done: bool = False, note_id: int | None = None) -> Reminder:
    row = Reminder(text=text, due_at=dt.datetime(2026, 11, 2, 9), done=done, entry_id=note_id)
    session.add(row)
    session.commit()
    return row


def _go(session, sentence: str) -> dict:
    parsed = acts.parse(sentence, NOW)
    assert parsed is not None, sentence
    return acts.preview(session, parsed)


def test_a_clear_match_completes_at_once_and_undo_reopens_it(session):
    target = _reminder(session, "Read chapter 5")
    _reminder(session, "Call the dentist")
    planned = _go(session, "mark read chapter 5 as done")
    assert planned["run"] and planned["card"]["steps"][0]["name"] == "complete_reminder"
    done = acts.run(session, planned["card"]["steps"])
    session.expire_all()
    assert done["ok"] and session.get(Reminder, target.id).done is True
    assert done["undo"] and done["undo"][0]["name"] == "complete_reminder"
    assert acts.run(session, done["undo"])["ok"]
    session.expire_all()
    assert session.get(Reminder, target.id).done is False


def test_a_fuzzy_match_finds_the_reminder_whatever_the_wording(session):
    target = _reminder(session, "Practice past paper 2")
    _reminder(session, "Pay rent")
    for sentence in ("tick off practice past paper", "complete the practice past paper task", "cross off past paper practice",
                     "check off the past paper reminder"):
        planned = _go(session, sentence)
        assert planned.get("card") and planned["card"]["steps"][0]["arguments"]["reminder_id"] == target.id, (sentence, planned)


def test_a_checklist_line_in_a_note_is_ticked_and_undo_unticks_it(session):
    note = manager.create_entry(session, "# History essay\n\nSources:\n- [ ] Hobsbawm chapter 2\n- [ ] Evans chapter 4\n- [x] Marx")
    session.commit()
    before = note.content
    planned = _go(session, "tick off hobsbawm chapter 2")
    assert planned["run"] and planned["card"]["steps"][0]["name"] == "edit_note"
    done = acts.run(session, planned["card"]["steps"])
    session.expire_all()
    assert done["ok"]
    assert manager.get_entry(session, note.id).content == before.replace("- [ ] Hobsbawm chapter 2", "- [x] Hobsbawm chapter 2")
    acts.run(session, done["undo"])
    session.expire_all()
    assert manager.get_entry(session, note.id).content == before


@pytest.mark.parametrize("sentence", ["complete the dentist reminder", "tick off dentist", "mark the dentist task as done"])
def test_an_ambiguous_match_asks_and_changes_nothing(session, sentence):
    a = _reminder(session, "Call the dentist")
    b = _reminder(session, "Dentist check-up")
    planned = _go(session, sentence)
    assert "card" not in planned and not planned.get("run")
    assert "Which" in planned["line"] and "Call the dentist" in planned["line"] and "Dentist check-up" in planned["line"], planned
    session.expire_all()
    assert not session.get(Reminder, a.id).done and not session.get(Reminder, b.id).done


def test_a_reminder_and_a_checklist_line_that_both_fit_are_asked_about(session):
    _reminder(session, "Read chapter 5")
    manager.create_entry(session, "# History\n\n- [ ] Evans chapter 4")
    session.commit()
    planned = _go(session, "tick off chapter")
    assert "card" not in planned and "Which" in planned["line"], planned
    assert "Read chapter 5" in planned["line"] and "Evans chapter 4" in planned["line"]


def test_the_reminder_word_keeps_a_checklist_line_out_of_it(session):
    target = _reminder(session, "Read the chapter")
    manager.create_entry(session, "# History\n\n- [ ] Evans chapter 4")
    session.commit()
    planned = _go(session, "complete the chapter reminder")
    assert planned["card"]["steps"][0]["arguments"]["reminder_id"] == target.id


def test_the_exact_name_beats_a_longer_one(session):
    short = _reminder(session, "Buy milk")
    _reminder(session, "Buy milk and eggs for the party")
    planned = _go(session, "tick off buy milk")
    assert planned["card"]["steps"][0]["arguments"]["reminder_id"] == short.id


def test_a_partial_match_is_asked_not_guessed(session):
    _reminder(session, "Call the dentist about the crown")
    planned = _go(session, "tick off call the plumber")
    assert "card" not in planned


def test_nothing_open_that_fits_says_so_and_a_done_one_is_not_a_candidate(session):
    _reminder(session, "Buy milk", done=True)
    planned = _go(session, "tick off buy milk")
    assert "card" not in planned and "found no" in planned["line"].lower(), planned


def test_a_task_on_a_private_note_is_never_touched(session):
    note = manager.create_entry(session, "# Secret\n\n- [ ] Buy a surprise gift")
    note.is_private = True
    session.commit()
    planned = _go(session, "tick off buy a surprise gift")
    assert "card" not in planned


def test_adding_a_task_is_a_reminder_card_that_undo_bins(session, clock):
    planned = _go(session, "add a task to read chapter 5 tomorrow")
    assert planned["run"] and "task" in planned["card"]["label"].lower()
    done = acts.run(session, planned["card"]["steps"])
    assert done["ok"] and done["undo"][0]["name"] == "bin_reminder"
    assert session.query(Reminder).count() == 1
    acts.run(session, done["undo"])
    session.expire_all()
    assert session.query(Reminder).filter(Reminder.deleted_at.is_(None)).count() == 0


def test_a_note_called_to_do_list_still_takes_the_line(session):
    note = manager.create_entry(session, "# To-do list\n\n- [ ] Post the form")
    session.commit()
    planned = _go(session, "add buy milk to my to-do list")
    step = planned["card"]["steps"][0]
    assert step["name"] == "edit_note" and step["arguments"]["note_id"] == note.id
    assert step["arguments"]["content"].endswith("Buy milk")
    assert session.query(Reminder).count() == 0


def test_with_no_such_note_the_same_sentence_is_a_task(session):
    planned = _go(session, "add buy milk to my to-do list tomorrow")
    assert planned["card"]["steps"][0]["name"] == "set_reminder"


# --- through the route -----------------------------------------------------------------------


def _stream(client, question: str, history: list | None = None) -> list[dict]:
    body = {"question": question, "use_tools": True, "history": history or []}
    with client.stream("POST", "/chat/stream", json=body) as response:
        return [json.loads(line) for line in response.iter_lines() if line.strip()]


@pytest.fixture
def clock(monkeypatch):
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)


def _said(events: list[dict]) -> str:
    return "".join(e.get("delta", "") for e in events if e["type"] == "answer")


def test_through_the_route_a_task_is_added_with_undo(client, session, clock):
    events = _stream(client, "add a task to read chapter 5 tomorrow")
    card = next(e for e in events if e["type"] == "act")
    assert card["done"] and card["undo"], card
    assert [r.text for r in session.query(Reminder)] == ["Read chapter 5"]


def test_through_the_route_a_task_with_no_time_is_asked_once(client, session, clock):
    events = _stream(client, "add chapter 5 reading to my to-do list")
    assert _said(events).rstrip().endswith("?") and "chapter 5 reading" in _said(events).lower()
    assert session.query(Reminder).count() == 0
    assert not any(e["type"] == "act" for e in events)


def test_through_the_route_a_task_is_completed_and_an_ambiguous_one_asks(client, session, clock):
    target = _reminder(session, "Buy milk")
    done = _stream(client, "tick off buy milk")
    assert next(e for e in done if e["type"] == "act")["done"]
    session.expire_all()
    assert session.get(Reminder, target.id).done is True
    _reminder(session, "Call the dentist")
    _reminder(session, "Dentist check-up")
    asked = _stream(client, "complete the dentist reminder")
    assert not any(e["type"] == "act" for e in asked) and "Which" in _said(asked)


# --- cancel, snooze (E10, second half) ---------------------------------------------------------

CANCEL = [
    ("cancel the dentist task", "dentist", None),
    ("delete the task buy milk", "buy milk", None),
    ("remove buy milk from my tasks", "buy milk", None),
    ("remove buy milk from my to-do list", "buy milk", None),
    ("delete the buy milk reminder", "buy milk", "reminder"),
    ("cancel the dentist reminder", "dentist", "reminder"),
    ("cancel task buy milk", "buy milk", None),
    ("scrap the buy milk task", "buy milk", None),
    ("take buy milk off my task list", "buy milk", None),
    ("please delete the hobsbawm checklist item", "hobsbawm", "checklist"),
    ("can you remove the dentist to-do", "dentist", None),
    # the owner's typos
    ("cancle the dentist task", "dentist", None),
    ("delte the task buy milk", "buy milk", None),
    ("remvoe buy milk from my tasks", "buy milk", None),
]


@pytest.mark.parametrize(("sentence", "about", "kind"), CANCEL)
def test_cancelling_a_task_names_it_in_the_persons_words(sentence, about, kind):
    got = commands.read_typed(sentence, NOW)
    assert got and got["intent"] == "cancel", got
    assert got["about"] == about and got.get("kind") == kind, got


NOT_CANCELLING = [
    ("delete the dentist note", "delete"),
    ("delete the boiler note", "delete"),
    ("cancel my subscription", None),
    ("remove the tag urgent from the boiler note", "untag"),
    ("delete all my tasks", None),
    ("what does cancel do", None),
    ("how do I delete a task?", None),
]


@pytest.mark.parametrize(("sentence", "intent"), NOT_CANCELLING)
def test_sentences_that_are_not_a_task_cancel_keep_their_reading(sentence, intent):
    got = commands.read_typed(sentence, NOW)
    assert (got or {}).get("intent") == intent, got


SNOOZE = [
    ("snooze the dentist task until friday", "dentist", None, FRIDAY_9),
    ("snooze the dentist reminder until friday", "dentist", "reminder", FRIDAY_9),
    ("push buy milk to tomorrow 5pm", "buy milk", None, dt.datetime(2026, 10, 29, 17, 0)),
    ("push back the dentist task to friday", "dentist", None, FRIDAY_9),
    ("postpone the dentist task to tomorrow", "dentist", None, TOMORROW_9),
    ("delay buy milk until friday", "buy milk", None, FRIDAY_9),
    ("move the dentist reminder to friday", "dentist", "reminder", FRIDAY_9),
    ("reschedule the buy milk task for tomorrow", "buy milk", None, TOMORROW_9),
    ("can you snooze buy milk till friday", "buy milk", None, FRIDAY_9),
    ("snoze the dentist task until friday", "dentist", None, FRIDAY_9),
    ("snooze buy milk until tomorow", "buy milk", None, TOMORROW_9),
    ("push buy milk to tomorow 5pm", "buy milk", None, dt.datetime(2026, 10, 29, 17, 0)),
]


@pytest.mark.parametrize(("sentence", "about", "kind", "due"), SNOOZE)
def test_snoozing_a_task_reads_the_name_and_the_time(sentence, about, kind, due):
    got = commands.read_typed(sentence, NOW)
    assert got and got["intent"] == "snooze", got
    assert got["about"] == about and got.get("kind") == kind and got["due_at"] == due, got


def test_snoozing_for_a_length_of_time_counts_from_now():
    got = commands.read_typed("snooze the dentist task for 2 hours", NOW)
    assert got and got["intent"] == "snooze" and got["due_at"] == NOW + dt.timedelta(hours=2), got


NOT_SNOOZING = [
    ("move the sourdough note to Cooking", "move"),
    ("move the dentist note to friday", "move"),
    ("push the code to main", None),
    ("what does snooze do", None),
    ("how do I snooze a reminder?", None),
]


@pytest.mark.parametrize(("sentence", "intent"), NOT_SNOOZING)
def test_sentences_that_are_not_a_snooze_keep_their_reading(sentence, intent):
    got = commands.read_typed(sentence, NOW)
    assert (got or {}).get("intent") == intent, got


def test_cancelling_a_reminder_bins_it_and_undo_restores_it(session):
    target = _reminder(session, "Call the dentist")
    other = _reminder(session, "Buy milk")
    planned = _go(session, "cancel the dentist task")
    assert planned["run"] and planned["card"]["steps"][0]["name"] == "bin_reminder"
    done = acts.run(session, planned["card"]["steps"])
    session.expire_all()
    assert done["ok"] and session.get(Reminder, target.id).deleted_at is not None
    assert session.get(Reminder, other.id).deleted_at is None
    assert done["undo"][0]["name"] == "restore_reminder"
    assert acts.run(session, done["undo"])["ok"]
    session.expire_all()
    assert session.get(Reminder, target.id).deleted_at is None


def test_cancelling_a_checklist_line_removes_it_and_undo_puts_it_back(session):
    note = manager.create_entry(session, "# History essay\n\nSources:\n- [ ] Hobsbawm chapter 2\n- [ ] Evans chapter 4\n- [x] Marx")
    session.commit()
    before = note.content
    planned = _go(session, "delete the hobsbawm checklist item")
    step = planned["card"]["steps"][0]
    assert planned["run"] and step["name"] == "edit_note"
    done = acts.run(session, planned["card"]["steps"])
    session.expire_all()
    after = manager.get_entry(session, note.id).content
    assert done["ok"] and "Hobsbawm" not in after and "- [ ] Evans chapter 4" in after and "- [x] Marx" in after
    acts.run(session, done["undo"])
    session.expire_all()
    assert manager.get_entry(session, note.id).content == before


def test_an_ambiguous_cancel_asks_and_binds_nothing(session):
    a = _reminder(session, "Call the dentist")
    b = _reminder(session, "Dentist check-up")
    planned = _go(session, "cancel the dentist task")
    assert "card" not in planned and "Which" in planned["line"], planned
    assert "Call the dentist" in planned["line"] and "Dentist check-up" in planned["line"]
    session.expire_all()
    assert session.get(Reminder, a.id).deleted_at is None and session.get(Reminder, b.id).deleted_at is None


def test_cancelling_what_is_not_there_says_so(session):
    _reminder(session, "Buy milk")
    planned = _go(session, "cancel the dentist task")
    assert "card" not in planned and "found no" in planned["line"].lower(), planned


def test_a_private_checklist_line_is_never_cancelled(session):
    note = manager.create_entry(session, "# Secret\n\n- [ ] Buy a surprise gift")
    note.is_private = True
    session.commit()
    assert "card" not in _go(session, "remove buy a surprise gift from my tasks")


def test_snoozing_a_reminder_moves_its_time_and_undo_puts_it_back(session):
    target = _reminder(session, "Call the dentist")
    was = target.due_at
    planned = _go(session, "snooze the dentist task until friday")
    assert planned["run"] and planned["card"]["steps"][0]["name"] == "snooze_reminder"
    done = acts.run(session, planned["card"]["steps"])
    session.expire_all()
    assert done["ok"] and session.get(Reminder, target.id).due_at.replace(tzinfo=None) == FRIDAY_9
    assert done["undo"][0]["name"] == "snooze_reminder"
    assert acts.run(session, done["undo"])["ok"]
    session.expire_all()
    assert session.get(Reminder, target.id).due_at.replace(tzinfo=None) == was


def test_snoozing_asks_which_when_two_fit(session):
    _reminder(session, "Call the dentist")
    _reminder(session, "Dentist check-up")
    planned = _go(session, "snooze the dentist task until friday")
    assert "card" not in planned and "Which" in planned["line"], planned


def test_a_checklist_line_cannot_be_snoozed_and_the_answer_says_so(session):
    manager.create_entry(session, "# History\n\n- [ ] Hobsbawm chapter 2")
    session.commit()
    planned = _go(session, "snooze the hobsbawm task until friday")
    assert "card" not in planned and "only reminders can be snoozed" in planned["line"].lower(), planned


def test_snoozing_with_no_readable_time_asks_until_when(session):
    target = _reminder(session, "Call the dentist")
    planned = _go(session, "snooze the dentist reminder")
    assert "card" not in planned and "until when" in planned["line"].lower(), planned
    session.expire_all()
    assert session.get(Reminder, target.id).due_at.replace(tzinfo=None) == dt.datetime(2026, 11, 2, 9)


def test_snoozing_to_a_time_that_has_passed_is_refused(session):
    # The run stores with restore=True, past the route's own check, so the plan refuses.
    target = _reminder(session, "Call the dentist")
    planned = _go(session, "snooze the dentist task until yesterday")
    assert "card" not in planned and "passed" in planned["line"], planned
    session.expire_all()
    assert session.get(Reminder, target.id).due_at.replace(tzinfo=None) == dt.datetime(2026, 11, 2, 9)


def test_through_the_route_a_task_is_cancelled_and_snoozed(client, session, clock):
    milk = _reminder(session, "Buy milk")
    dentist = _reminder(session, "Call the dentist")
    snoozed = _stream(client, "push call the dentist to tomorrow 5pm")
    assert next(e for e in snoozed if e["type"] == "act")["done"]
    session.expire_all()
    assert session.get(Reminder, dentist.id).due_at.replace(tzinfo=None) == dt.datetime(2026, 10, 29, 17, 0)
    cancelled = _stream(client, "cancel the buy milk task")
    card = next(e for e in cancelled if e["type"] == "act")
    assert card["done"] and card["undo"]
    session.expire_all()
    assert session.get(Reminder, milk.id).deleted_at is not None



def test_a_snooze_within_hours_says_for_how_long(client, session, clock):
    """Audit 1029 C47: never "Snooze “x” to in 2 hours"."""
    _reminder(session, "Call the dentist")
    card = next(e for e in _stream(client, "snooze the dentist task for 2 hours") if e["type"] == "act")
    assert card["label"].startswith("Snooze “Call the dentist” for 2 hours, at "), card["label"]
