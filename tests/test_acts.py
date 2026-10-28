"""The act registry (CHAT_PLAN module 3, decision 53; Brief 67): every act
has parse, preview, run, an inverse and a help line; every write act run and
then undone leaves the notebook as it was; the capability line, the Guide's
act topic and Ask's line are generated from it; a model's proposed act is
previewed through it and never runs on its own word."""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import select

from tessellate.ai import acts, commands, help_chat
from tessellate.core.database import Entry, EntryLink, Reminder
from tessellate.entry import manager

NOW = datetime(2026, 10, 10, 12, 0)


def _seed(session):
    for content in (
        "# Boiler service\n\nDue in March. The engineer said the valve was worn.",
        "# Gym log\n\nSquats on Monday, five sets of five.",
        "# Running\n\nRan 5 km on Saturday.",
        "# Knife care\n\nHone before each use.",
        "# Sourdough\n\nFeed the starter at night.",
        "# Dentist\n\nCheck-up on the 21st.",
    ):
        manager.create_entry(session, content)
    session.commit()


def _state(session) -> tuple:
    """Everything an act may change, as plain values."""
    session.expire_all()
    notes = tuple(
        (e.id, e.content, e.category_id, e.tags, e.pinned, e.deleted_at is None)
        for e in session.scalars(select(Entry).order_by(Entry.id))
        if e.deleted_at is None
    )
    links = tuple(sorted((link.source_entry_id, link.target_entry_id) for link in session.scalars(select(EntryLink))))
    reminders = tuple((r.id, r.done, r.due_at) for r in session.scalars(select(Reminder)) if r.deleted_at is None)
    return notes, links, reminders


def test_every_act_has_parse_preview_run_and_a_help_line():
    for act in acts.ACTS.values():
        parsed = acts.parse(act.example, NOW)
        assert parsed and parsed["intent"] == act.intent, act.example
        assert act.help and act.label and not act.help.endswith("!")
        assert acts.missing(parsed) == [], act.example
    assert set(acts.ACTS) >= set(commands.WRITE_INTENTS) | set(commands.READ_INTENTS)


WRITES = [a for a in acts.ACTS.values() if a.writes]
#: An unpin, an unlink or an untag needs its pin, link or tag first.
_BEFORE = {"unpin": "pin the dentist note", "unlink": "link the gym note to the running note", "untag": "tag the boiler note with urgent"}


@pytest.mark.parametrize("act", WRITES, ids=[a.intent for a in WRITES])
def test_every_write_act_has_an_inverse_that_restores_the_notebook(client, session, act):
    _seed(session)
    if act.intent in _BEFORE:
        setup = acts.preview(session, acts.parse(_BEFORE[act.intent], NOW))
        acts.run(session, setup["card"]["steps"])
        session.commit()
    if act.intent in ("complete", "cancel", "snooze"):
        #: A task is completed, cancelled or snoozed only once one is open;
        #: seeded directly, as the store refuses a reminder due before the
        #: real clock.
        session.add(Reminder(text="Buy milk" if act.intent == "complete" else "Call the dentist", due_at=datetime(2030, 1, 1, 9)))
        session.commit()
    before = _state(session)
    # The store refuses a reminder due in the past by the real clock, so a
    # fixed NOW turns "on Friday" into a past date once that week is over.
    now = datetime.now().replace(hour=12, minute=0, second=0, microsecond=0) if act.intent == "reminder" else NOW
    planned = acts.preview(session, acts.parse(act.example, now))
    card = planned["card"]
    assert card["steps"], act.intent
    done = acts.run(session, card["steps"], card.get("skipped"))
    session.commit()
    assert done["ok"], (act.intent, done)
    assert _state(session) != before, f"{act.intent} changed nothing"
    assert done["undo"] and done["undo"][0]["name"] == act.inverse, (act.intent, done["undo"])
    undone = acts.run(session, done["undo"])
    session.commit()
    assert undone["ok"], (act.intent, undone)
    assert _state(session) == before, act.intent


def test_read_acts_have_no_inverse_and_write_acts_all_do():
    assert all(a.inverse for a in WRITES)
    assert not any(a.inverse for a in acts.ACTS.values() if not a.writes)


def test_the_capability_line_is_the_registry_said():
    line = acts.capability_line()
    assert line == commands.CAPABILITY_LINE
    for act in acts.ACTS.values():
        if act.writes and act.intent not in ("untag", "unpin", "unlink", "append"):
            assert act.verb in line or act.label in line, act.label


def test_the_guide_topic_is_generated_from_the_registry():
    topic = next(t for t in help_chat.HELP_TOPICS if t["id"] == "chat-acts")
    for act in acts.ACTS.values():
        assert act.example in topic["body"]
    assert help_chat.topics_for("what can chat do with no model")[0]["id"] == "chat-acts"


def test_ask_names_the_act_it_read():
    assert acts.ask_line(acts.parse("delete the boiler note", NOW)) == (
        "That is something to do (delete a note) rather than to look up: say it in Chat and it is done there, with Undo."
    )


def test_a_models_proposed_act_waits_for_confirm(client, session):
    """Decision 53: a reminder typed runs at once; the same act proposed by a
    model is a card that waits for Confirm."""
    _seed(session)
    typed = acts.preview(session, acts.parse("remind me to call mum on Friday at 9", NOW))
    proposed = acts.propose(session, "remind me to call mum on Friday at 9", NOW)
    assert typed.get("run") is True
    assert "run" not in proposed and proposed["card"]["proposed"] is True
    assert acts.propose(session, "what is the boiler pressure?", NOW) is None


def test_palette_rows_come_from_the_registry():
    rows = acts.palette_rows()
    assert [r["intent"] for r in rows] == list(acts.ACTS)
    assert all(r["label"][:1].isupper() and r["example"] for r in rows)


#: INBOX 734: ten ways of saying one reminder.
DENTIST = (
    "remind me to call the dentist on Friday at 9",
    "remind me on Friday at 9 to call the dentist",
    "remind me friday at 9am to call the dentist",
    "remind me to call the dentist friday 9am",
    "on friday at 9 remind me to call the dentist",
    "remind me to call the dentist at 9 on friday",
    "please remind me to call the dentist on Friday at 9",
    "can you remind me to call the dentist friday at 9:00",
    "remind me to call the dentist this friday at 9",
    "set a reminder to call the dentist on friday at 9",
)


@pytest.mark.parametrize("phrase", DENTIST)
def test_a_reminder_is_said_back_with_the_note_it_comes_from(client, session, monkeypatch, phrase):
    """INBOX 734 on the route: the card says "Remind you on Friday at 9: call
    the dentist", names the Dentist note and attaches the reminder to it; the
    words after the colon are the person's own (grounded in what they typed)."""
    from tessellate.api import routes_chat
    from tests.test_composer_route_688 import _ask

    monkeypatch.setattr("tessellate.core.config.user_now", lambda _config: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _config: NOW)
    _seed(session)
    dentist = session.scalars(select(Entry).where(Entry.content.like("# Dentist%"))).one()
    out = _ask(client, phrase, use_tools=False)
    card = out["act"][0]
    assert card["label"] == "Remind you on Friday at 9: call the dentist", phrase
    assert card["items"] == [f"#{dentist.id} Dentist"]
    assert card["steps"][0]["arguments"]["note_id"] == dentist.id
    #: Said back in the composer's words (CHAT_PLAN 1353), the card's label exact.
    assert out["text"].endswith("remind you on Friday at 9: call the dentist.") and "!" not in out["text"], out["text"]
    assert "call the dentist" in phrase.lower()
    reminder = session.scalars(select(Reminder)).one()
    assert reminder.entry_id == dentist.id and reminder.due_at.strftime("%a %H:%M") == "Fri 09:00"


@pytest.mark.parametrize(
    ("due", "said"),
    [(datetime(2026, 10, 10, 17, 0), "today at 5pm"), (datetime(2026, 10, 11, 9, 30), "tomorrow at 9:30"),
     (datetime(2026, 10, 16, 12, 0), "on Friday at noon"), (datetime(2026, 10, 21, 8, 0), "on 21 October at 8"),
     (datetime(2027, 1, 4, 9, 0), "on 4 January 2027 at 9")],
)
def test_reminder_when_says_the_time_against_today(due, said):
    assert commands.reminder_when(due, NOW) == said
