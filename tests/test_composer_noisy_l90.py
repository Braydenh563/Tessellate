"""L90 and L91 (audit 1031 C4 and C5): in a notebook with 150 filler notes the
note that defines the subject is told, ahead of the filler, and no filler note
is quoted at length. Notebook and clock: `tests/_seed_1031c.py`."""

from __future__ import annotations

import re

import pytest

from tests.test_composer_cfix_1031 import _a_fixed_day, big_notebook  # noqa: F401

QUOTE = re.compile(r"“([^”]+)”")


@pytest.mark.parametrize("question", ["what do I know about reading", "what do I know about the books I read"])
def test_the_defining_note_is_told_in_the_first_paragraph(big_notebook, question):  # noqa: F811
    said, _ = big_notebook(question)
    paragraphs = said.split("\n")
    assert "Piranesi" in said, said[:600]
    assert any("Piranesi" in p for p in paragraphs[:3]), paragraphs[:3]


@pytest.mark.parametrize("question", [
    "what do I know about reading", "what do I know about the dentist", "what do I know about travel", "what do I know about health",
])
def test_no_filler_note_is_quoted_at_length(big_notebook, question):  # noqa: F811
    said, _ = big_notebook(question)
    longest = max((len(q.split()) for q in QUOTE.findall(said)), default=0)
    assert longest <= 14, (longest, said[:800])
