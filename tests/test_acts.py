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
from tessellate.core.database import Document, Entry, EntryLink, Reminder, UserPreference, WhiteboardNode
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


def _state(session, categories: bool = False, by_name: bool = False) -> tuple:
    """Everything an act may change, as plain values. The category by its id and by its
    name: a rename keeps the id, so the id alone cannot see rename_category change anything."""
    session.expire_all()
    notes = tuple(
        (e.id, e.content, None if by_name else e.category_id, manager.category_name_for(session, e), e.tags, e.pinned, e.deleted_at is None)
        for e in session.scalars(select(Entry).order_by(Entry.id))
        if e.deleted_at is None
    )
    links = tuple(sorted((link.source_entry_id, link.target_entry_id) for link in session.scalars(select(EntryLink))))
    reminders = tuple((r.id, r.done, r.due_at) for r in session.scalars(select(Reminder)) if r.deleted_at is None)
    #: The name is a preference, not a row: set_name changes it (G7).
    from tessellate.core import deps

    #: A category made with no note in it is a row of its own: create_category changes it (parity, 1110).
    #: Read only for that act, since a move leaves the category it made behind when it is undone.
    from tessellate.core.database import Category

    made = tuple(sorted(c.name for c in session.scalars(select(Category)))) if categories else ()
    #: The surface acts (L-chat-26): documents, saved skills and the cards on the board.
    surfaces = (
        tuple(sorted((d.title, d.content) for d in session.scalars(select(Document)))),
        #: By name: Undo saves the skill again with its defaults filled in.
        tuple(sorted(str(s.get("name")) for s in deps.get_config().get_preference("skills", []))),
        tuple(sorted(n.entry_id for n in session.scalars(select(WhiteboardNode)))),
        #: A suggested preference (remember, L114) is a row that waits for an answer; its Undo drops it.
        tuple(sorted(p.content for p in session.scalars(select(UserPreference)))),
    )
    return notes, links, reminders, deps.get_config().get_preference("display_name", ""), made, surfaces


def test_every_act_has_parse_preview_run_and_a_help_line():
    for act in acts.ACTS.values():
        parsed = acts.parse(act.example, NOW)
        assert parsed and parsed["intent"] == act.intent, act.example
        assert act.help and act.label and not act.help.endswith("!")
        assert acts.missing(parsed) == [], act.example
    assert set(acts.ACTS) >= set(commands.WRITE_INTENTS) | set(commands.READ_INTENTS)


WRITES = [a for a in acts.ACTS.values() if a.writes]
#: An unpin, an unlink or an untag needs its pin, link or tag first.
_BEFORE = {
    "unpin": "pin the dentist note", "unlink": "link the gym note to the running note", "untag": "tag the boiler note with urgent",
    #: A tag, a category and a binned note must exist before they are renamed or restored.
    "rename_tag": "tag the gym note with gym", "rename_category": "move the gym note to Work", "restore": "delete the passport note",
    #: Parity acts (1110): the category, the tag, the two categories a merge needs.
    "delete_category": ("move the gym note to Hobbies",), "delete_tag": ("tag the gym note with harbor",),
    "merge_categories": ("move the gym note to Work", "move the running note to Job"),
}
_PAGE_SIDE = frozenset({"set_theme"})
#: A category row is made again by Undo with a new id, so these compare the categories by name.
_BY_NAME = frozenset({"delete_category", "merge_categories"})


@pytest.mark.parametrize("act", WRITES, ids=[a.intent for a in WRITES])
def test_every_write_act_has_an_inverse_that_restores_the_notebook(client, session, act):
    _seed(session)
    if act.intent == "delete_document":
        session.add(Document(title="Harbor report", content="Findings for the harbor."))
        session.commit()
    if act.intent == "delete_skill":
        from tessellate.core import deps

        deps.get_config().set_preference("skills", [{"name": "Weekly tidy", "prompt": "Tidy my notes.", "steps": []}])
    if act.intent == "restore":
        manager.create_entry(session, "# Passport\n\nRenew in May.")
        session.commit()
    if act.intent == "edit_text":
        manager.create_entry(session, "# Wifi\n\nNetwork is Bluegum-5G.")
        session.commit()
    if act.intent == "to_reminders":
        manager.create_entry(session, "# Action items\n\n- [ ] book the venue\n- [ ] email the caterer\n")
        session.commit()
    for before_sentence in (lambda x: (x,) if isinstance(x, str) else x)(_BEFORE.get(act.intent, ())):
        setup = acts.preview(session, acts.parse(before_sentence, NOW))
        acts.run(session, setup["card"]["steps"])
        session.commit()
    if act.intent == "uncomplete":
        session.add(Reminder(text="Buy milk", due_at=datetime(2030, 1, 1, 9), done=True))
        session.commit()
    if act.intent in ("complete", "cancel", "snooze"):
        #: A task is completed, cancelled or snoozed only once one is open;
        #: seeded directly, as the store refuses a reminder due before the
        #: real clock.
        session.add(Reminder(text="Buy milk" if act.intent == "complete" else "Call the dentist", due_at=datetime(2030, 1, 1, 9)))
        session.commit()
    before = _state(session, act.intent in ("create_category", *_BY_NAME), act.intent in _BY_NAME)
    # The store refuses a reminder due in the past by the real clock, so a
    # fixed NOW turns "on Friday" into a past date once that week is over
    # (a snooze too: its plan refuses a time already passed on the real clock).
    now = datetime.now().replace(hour=12, minute=0, second=0, microsecond=0) if act.intent in ("reminder", "snooze", "to_reminders") else NOW
    planned = acts.preview(session, acts.parse(act.example, now))
    card = planned["card"]
    assert card["steps"], act.intent
    done = acts.run(session, card["steps"], card.get("skipped"))
    session.commit()
    assert done["ok"], (act.intent, done)
    #: The theme is the page's preference, not the server's: the step acknowledges it (tests/test_chat_acts_2_1112_d.py).
    assert act.intent in _PAGE_SIDE or _state(session, act.intent in ("create_category", *_BY_NAME), act.intent in _BY_NAME) != before, f"{act.intent} changed nothing"
    assert done["undo"] and done["undo"][0]["name"] == act.inverse, (act.intent, done["undo"])
    undone = acts.run(session, done["undo"])
    session.commit()
    assert undone["ok"], (act.intent, undone)
    assert _state(session, act.intent in ("create_category", *_BY_NAME), act.intent in _BY_NAME) == before, act.intent


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
    """Decision 53, moved by the owner's consent order (2026-11-10): a reminder typed and
    the same act proposed by a model are both a card that waits for Confirm."""
    _seed(session)
    typed = acts.preview(session, acts.parse("remind me to call mum on Friday at 9", NOW))
    proposed = acts.propose(session, "remind me to call mum on Friday at 9", NOW)
    assert "run" not in typed and typed["card"]["steps"] == proposed["card"]["steps"]
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
    assert card["label"] == "Remind you on Friday at 9am: call the dentist", phrase
    #: Audit 1028 E64 moved the intent: the note is named by its title, not "#id".
    assert card["items"] == ["Dentist"]
    assert card["steps"][0]["arguments"]["note_id"] == dentist.id
    #: Said back in the composer's words (CHAT_PLAN 1353), the card's label exact.
    assert "remind you on friday at 9am: call the dentist" in out["text"].lower() and "!" not in out["text"], out["text"]
    assert "call the dentist" in phrase.lower()
    assert session.scalars(select(Reminder)).all() == [], "nothing is set before Confirm"
    from tests._consent import confirmed

    done = confirmed(client, out)  # Confirm words the run as the composer did before the consent order
    assert done["text"].endswith("remind you on Friday at 9am: call the dentist.") and "!" not in done["text"], done["text"]
    session.expire_all()
    reminder = session.scalars(select(Reminder)).one()
    assert reminder.entry_id == dentist.id and reminder.due_at.strftime("%a %H:%M") == "Fri 09:00"


@pytest.mark.parametrize(
    ("due", "said"),
    [(datetime(2026, 10, 10, 17, 0), "today at 5pm"), (datetime(2026, 10, 11, 9, 30), "tomorrow at 9:30am"),
     (datetime(2026, 10, 16, 12, 0), "on Friday at noon"), (datetime(2026, 10, 21, 8, 0), "on 21 October at 8am"),
     (datetime(2027, 1, 4, 9, 0), "on 4 January 2027 at 9am")],
)
def test_reminder_when_says_the_time_against_today(due, said):
    assert commands.reminder_when(due, NOW) == said


@pytest.mark.parametrize(
    ("due", "said"),
    [(datetime(2026, 10, 10, 14, 0), "in 2 hours, at 2pm"), (datetime(2026, 10, 10, 12, 45), "in 45 minutes, at 12:45pm"),
     (datetime(2026, 10, 10, 13, 0), "in an hour, at 1pm"), (datetime(2026, 10, 10, 14, 20), "in about 2 hours, at 2:20pm")],
)
def test_a_reminder_within_three_hours_says_how_soon(due, said):
    """Audit 1029 C47: "remind me in 2 hours" was said back as "today at
    2:32am", which reads as a mistake; within three hours it says how soon."""
    assert commands.reminder_when(due, NOW) == said
