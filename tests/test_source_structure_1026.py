"""A board's card or a map's node is not a heading (composer9 Remaining,
"summarise my uni notes" said a mind-map node as "**Service models:**").

The class: a non-note source keeps its own structure (a node, a card, a child
under a parent). A line of it written "IaaS: renting servers" is the node's
text, said whole; only a note's own "Heading: text" sentence becomes a bold
label. Said any way a digest is asked for."""

from __future__ import annotations

import datetime as dt
import re

import pytest

from tessellate.ai import composer_digest as digest

TODAY = dt.date(2026, 10, 21)

ASKED = [
    "summarise my uni notes",
    "summarize my uni notes",
    "sum up my uni notes",
    "give me a summary of my uni notes",
    "what's in my uni notes",
    "catch me up on uni",
]

MAP = "# Cloud computing map\n\n- Service models\n  - IaaS: renting servers\n  - PaaS: a platform\n- Deployment\n  - Public cloud"
BOARD = "# Revision board\n\n- Cards for the exam\n- Scheduling: round robin\n- Deadline: 30 October"
NOTE = "# Study plan\n\nStudy plan: two hours each evening."


def _row(i: int, content: str, kind: str | None) -> dict:
    row = {
        "id": i, "content": content, "category": "Uni", "tags": [],
        "created_at": f"2026-10-{10 + i:02d}T09:00:00", "updated_at": f"2026-10-{10 + i:02d}T09:00:00",
    }
    if kind:
        row["kind"] = kind
    return row


def _ask(question: str, *rows: dict) -> str:
    out = digest.answer(question, list(rows), today=TODAY)
    return out["text"] if out else ""


def _label_of(text: str, word: str) -> bool:
    return bool(re.search(rf"\*\*{re.escape(word)}:\*\*", text))


@pytest.mark.parametrize("question", ASKED)
@pytest.mark.parametrize("word", ["IaaS", "PaaS", "Scheduling", "Deadline"])
def test_a_node_or_card_is_not_said_as_a_heading(question, word):
    text = _ask(question, _row(1, "# Uni timetable\n\nMy uni days this week are Tuesday and Thursday.", None), _row(2, MAP, "map"), _row(3, BOARD, "board"))
    assert text, question
    assert not _label_of(text, word), text


#: "give me a summary of" is the one-note digest: it picks the best note, so a
#: node's words are not in it, whichever source that is.
WHOLE = [q for q in ASKED if not q.startswith("give me")]


@pytest.mark.parametrize("question", WHOLE)
def test_a_node_keeps_its_own_words(question):
    text = _ask(question, _row(1, "# Uni timetable\n\nMy uni days this week are Tuesday and Thursday.", None), _row(2, MAP, "map"), _row(3, BOARD, "board"))
    assert re.search(r"renting servers", text), text
    assert re.search(r"round robin", text), text


def test_a_note_keeps_its_own_heading_label():
    """The control: a note's "Study plan: ..." sentence is still a label."""
    text = _ask("summarise my uni notes", _row(1, NOTE, None), _row(2, "# Other\n\nThe other one is about the garden.", None))
    assert "two hours each evening" in text
