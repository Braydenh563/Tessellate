"""L-chat-223 and 224 (CHAT_PLAN section 8 rows 3 and 4): a 30-question set
across every kind (notes, reminders, documents, boards, files), each answered
from the app's own rows with no model, and each answer shaped as its question
asks: a count in one line, a list as a list, a comparison as a table. The
clock is Monday 9 November 2026."""

from __future__ import annotations

from datetime import datetime

import pytest

import tests._seed_r9_1109 as sd
from tessellate.core.database import Attachment, Document, Reminder
from tessellate.entry import manager


@pytest.fixture
def ask(client, session, monkeypatch):
    ids = sd.seed(session)
    session.add_all([
        Document(title="Harbor report", content="Findings for the harbor. The quay needs repairs.", updated_at=datetime(2026, 6, 12, 10)),
        Document(title="Q4 plan", content="Sales and churn targets.", updated_at=datetime(2026, 11, 2, 10)),
        Document(title="Garden notes", content="Beds, seeds and the shed.", updated_at=datetime(2026, 6, 20, 10)),
        Reminder(text="Call plumber", due_at=datetime(2026, 11, 11, 9)),
        Reminder(text="Pay council tax", due_at=datetime(2026, 11, 13, 9)),
        Attachment(entry_id=ids[0], filename="starter-photo.jpg", stored_name="abc123", mime="image/jpeg", size=10, created_at=datetime(2026, 10, 3, 9)),
        Attachment(entry_id=ids[3], filename="invoice-marek.pdf", stored_name="def456", mime="application/pdf", size=10, created_at=datetime(2026, 6, 4, 9)),
    ])
    for title, when in (("Harbor plan board", datetime(2026, 6, 8, 10)), ("Kitchen layout board", datetime(2026, 10, 20, 10))):
        board = manager.create_entry(session, f"# {title}\n\nA board.", category_name="Uncategorised")
        board.is_board = True
        board.created_at = board.updated_at = when
    session.commit()
    go = sd.asker(client, monkeypatch, chat=True)
    return lambda question: go(question)[0]


#: (question, a word the answer must hold)
ANSWERED = [
    ("what is due this week", "Call plumber"),
    ("what reminders do I have", "Pay council tax"),
    ("how many reminders are overdue", "no overdue"),
    ("my documents about the harbor", "Harbor report"),
    ("documents from June", "Garden notes"),
    ("which documents mention the quay", "Harbor report"),
    ("show me documents about churn", "Q4 plan"),
    ("do I have any documents about submarines", "no documents"),
    ("which documents do I have", "Q4 plan"),
    ("how many documents do I have", "3 documents"),
    ("boards from June", "Harbor plan board"),
    ("boards about the kitchen", "Kitchen layout board"),
    ("my whiteboards from October", "Kitchen layout board"),
    ("any boards about volcanoes", "no boards"),
    ("files named invoice", "invoice-marek.pdf"),
    ("files from October", "starter-photo.jpg"),
    ("do I have a file called starter", "starter-photo.jpg"),
    ("files about the lighthouse", "no files"),
    ("how many notes do I have", "50 notes"),
    ("what did I write about the kitchen", "kitchen"),
    ("what is Doug", "starter"),
    ("when is my doctor appointment", "13 November"),
    ("who is Raj", "manager"),
    ("when does my car insurance renew", "28 November"),
    ("what is 15% of 240", "36"),
    ("what is the plumber's number", "07700 900789"),
    ("when is the Q4 report due", "20 November"),
    ("what is the kitchen budget", "8,000"),
    ("how many days until Christmas", "25 December"),
    ("what tags do I have", "tags"),
]
assert len(ANSWERED) == 30


@pytest.mark.parametrize(("question", "holds"), ANSWERED, ids=[q for q, _ in ANSWERED])
def test_each_kind_answers_from_its_own_rows(ask, question: str, holds: str) -> None:
    assert holds.lower() in ask(question).lower()


def test_the_shape_follows_the_question(ask) -> None:
    count = ask("how many documents do I have")
    assert "\n" not in count.strip()  # a count is one line
    listed = ask("my documents about the harbor")
    assert listed.count("\n- ") >= 1 and "[Harbor report](#/docs/" in listed  # a list is a list with its link
    boards = ask("boards from June")
    assert "(#/library/board/" in boards
    table = ask("which documents do I have")
    assert "| Document |" in table  # the listing keeps its table
    refused = ask("do I have any documents about submarines")
    assert refused.strip().endswith(".") and "\n" not in refused.strip()


def test_no_answer_in_the_set_says_a_sentence_twice_or_shouts(ask) -> None:
    """The maxims, as far as a streamed string shows them: quantity (no sentence
    said twice), manner (no shouting)."""
    import re

    for question, _ in ANSWERED:
        said = ask(question)
        sentences = [s.strip().lower() for s in re.split(r"(?<=[.?!])\s+|\n+", re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", said)) if len(s.strip()) > 12]
        assert len(sentences) == len(set(sentences)), (question, said)
        assert "!" not in said, (question, said)


@pytest.mark.parametrize("question", ["show my notes as a table", "list my notes in a table"])
def test_notes_asked_as_a_table_come_as_a_table(ask, question: str) -> None:
    """L-chat-253: the same newest notes, drawn as a table, not "I am not sure I can do that"."""
    said = ask(question)
    assert "| Note |" in said and "(#/notes/" in said, said
    assert "not sure" not in said
