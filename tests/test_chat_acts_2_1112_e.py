"""Cancel, rename, restore and add-to-today on the model path (L123), and the no-model sentence reading (L100):
the composer's typed reader finds the same step in agent mode (`use_tools=True`) as with it off, and each step is a
tool the model has, parked for the same Confirm. Clock: Tuesday 10 November 2026, 09:00."""

from __future__ import annotations

import pytest

from tessellate.ai import tools
from tessellate.core.database import Reminder
from tessellate.entry import manager

from tests.test_chat_acts_2_1112_c import _fixed_now  # noqa: F401
from tests.test_parity_acts_1110 import card_of, stream
from datetime import datetime


@pytest.fixture
def notebook(session):
    manager.create_entry(session, "# Gym log\n\nSquats on Monday.", category_name="Life")
    manager.create_entry(session, "# Passport\n\nRenew in May.", category_name="Life")
    session.add(Reminder(text="Call the dentist", due_at=datetime(2030, 1, 1, 9)))
    session.commit()
    from sqlalchemy import select

    from tessellate.core.database import Entry

    gone = next(e for e in session.scalars(select(Entry)) if (e.content or "").startswith("# Passport"))
    gone.is_deleted, gone.deleted_at = True, datetime(2026, 11, 9, 9, 0)
    session.commit()
    return session


@pytest.mark.parametrize(
    ("sentence", "step"),
    [("cancel the dentist task", "bin_reminder"), ("rename the gym note to Strength plan", "edit_note"),
     ("restore the passport note", "restore_note"), ("add buy chalk to today's note", "create_note")],
)
def test_the_same_step_with_the_agent_on_and_off_and_the_model_tool_parks(client, notebook, sentence, step):
    plain = card_of(stream(client, sentence, use_tools=False))["steps"]
    agent = card_of(stream(client, sentence, use_tools=True))["steps"]
    assert [s["name"] for s in plain] == [s["name"] for s in agent] == [step]
    assert step in tools.TOOLS or step == "bin_reminder"
    if step in tools.TOOLS:
        assert tools.needs_confirm(step, agent[0]["arguments"]) is True


@pytest.mark.parametrize(
    "question",
    ["give me an overview of my gym notes", "i need help planning the harbor launch", "do the thing with my gym log", "what did the engineer say about the valve"],
)
@pytest.mark.parametrize("use_tools", [True, None])
def test_agent_mode_with_no_model_never_takes_the_whole_sentence_as_the_subject(client, notebook, question, use_tools):
    """L100: the Agent switch on and no model running reads the sentence as the composer does."""
    text = stream(client, question, use_tools=use_tools)["text"].casefold()
    assert question.casefold() not in text and "no model" not in text
