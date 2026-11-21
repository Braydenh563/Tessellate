"""'ai is cool' against a notebook that has a Sketches category (IDEAS.md, "I
wrote 'ai is cool' as a note and it was filed under sketches": check that
filing against the notebook's categories; L-world-class-186). The meaning path
is `tests/test_janitor_short.py`; this is the words path, which files when no
embedding model runs, over the 120-note fixture plus drawings with captions."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tessellate.ai import lexical_filing
from tessellate.entry import manager

NOTES = json.loads((Path(__file__).parent / "fixtures" / "filing" / "notes.json").read_text(encoding="utf-8"))
SKETCHES = [
    "Garden layout ![sketch](/media/garden.png)",
    "Rough idea for the logo ![sketch](/media/logo.png)",
    "Cat drawing ![sketch](/media/cat.png)",
    "Kitchen shelves, side view ![sketch](/media/shelves.png)",
]


@pytest.fixture
def notebook(session):
    for note in NOTES:
        manager.create_entry(session, note["content"], category_name=note["category"])
    for text in SKETCHES:
        manager.create_entry(session, text, category_name="Sketches")
    session.commit()
    return session


@pytest.mark.parametrize("text", ["ai is cool", "AI is cool", "ai is so cool", "i think ai is cool"])
def test_a_short_note_about_ai_is_never_filed_under_sketches(notebook, text):
    call = lexical_filing.filing_call(notebook, text)
    assert call.category != "Sketches", call
    assert "Sketches" not in [name for name, _why in call.choices], call
