"""The Guide on the reading (CHAT_PLAN decision 59, step 4; Brief 84): a
how-to that reads as a note act is answered from the act registry, the
keyword rules stay as the fallback band, and the offline answer leads with
the one line Chat's help register gives, the preface after it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tessellate.ai import act_registry, composer, help_chat, reading

#: Importing `reading` sets the Guide's reader hook on the act registry (act_registry.py).
READER_LOADED = reading.__name__

BANK = json.loads((Path(__file__).parent / "fixtures" / "help_questions.json").read_text(encoding="utf-8"))


def test_the_bank_holds_its_first_time_right_count():
    right = sum(1 for q, want in BANK if (help_chat.topics_for(q) or [{}])[0].get("id") == want)
    #: 171 of 177 before the reading band and after it (measured 2026-10-10).
    assert right >= 171


@pytest.mark.parametrize(("question", "act"), [("how do I pin a note", "pin"), ("how do I rename a note", "rename"),
                                                ("how can I unlink two notes", "unlink")])
def test_a_note_act_howto_is_answered_from_the_registry(question, act):
    topics = help_chat.topics_for(question)
    assert topics[0]["id"] == f"act-{act}"
    assert act_registry.ACTS[act].example in topics[0]["body"]


def test_a_howto_about_another_surface_keeps_its_topic():
    assert help_chat.topics_for("how do i rename a category")[0]["id"] == "manage-categories"
    assert help_chat._act_of("how do I add a branch to a mind map") is None


def test_the_topic_that_explains_an_act_stays_first():
    ids = [t["id"] for t in help_chat.topics_for("how can I delete a note")]
    assert ids[:2] == ["undo-bin", "act-delete"]


def test_the_offline_guide_answers_first_in_chats_help_line():
    question = "how do I export my notes"
    reply = help_chat.offline_answer(question)["content"]
    line, _ = composer.help_line(question, help_chat.topics_for(question))
    assert reply.startswith(line)
    #: INBOX 1414: the "From the help" byline says where it came from, so the text does not.
    assert help_chat.OFFLINE_LEAD not in reply
