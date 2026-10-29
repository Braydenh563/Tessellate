"""INBOX 1301 D5 follow-up: a label that only opens a sentence is said as prose.

List rows (a time, a page title, a capability group) keep their bold label."""
from __future__ import annotations

import re
from datetime import date

from tessellate.ai import composer, composer_digest

LABEL_OPENER = re.compile(r"^\*\*[^*\n]{1,40}:\*\*", re.M)


def _views(notes):
    return [composer.read_note(n, 0) for n in notes]


def test_who_says_days_as_clauses_and_keeps_names_capitalised():
    notes = [
        {"id": i, "content": f"# T{i}\n\nPriya moved to Leeds in spring.", "tags": [], "category": "x", "created_at": f"2026-09-0{i}T10:00:00"}
        for i in (1, 2, 3)
    ]
    #: Asked about time, each day is a clause (INBOX 1441: a day is said
    #: only then); not asked, the same line is said once, undated.
    composer_digest._set_timing("when did Priya come up?")
    out = composer_digest._Out()
    assert composer_digest._who(out, "priya", _views(notes), set(), date(2026, 10, 11))
    text = "\n".join(out.lines)
    assert not LABEL_OPENER.search(text), text
    assert "On 2 September, Priya moved to Leeds in spring." in text, text
    composer_digest._set_timing("who is Priya?")
    out = composer_digest._Out()
    assert composer_digest._who(out, "priya", _views(notes), set(), date(2026, 10, 11))
    assert out.lines[1:] == ["Priya moved to Leeds in spring."], out.lines


def test_still_open_extra_is_a_sentence():
    notes = [
        {"id": 1, "content": "# Groceries\n\nNeed to buy: milk, eggs, bread.", "tags": ["shopping"], "category": "Home", "created_at": "2026-10-02T10:00:00"},
        {"id": 2, "content": "# Trip\n\nThe tent is still to buy.", "tags": ["camping"], "category": "Home", "created_at": "2026-10-03T10:00:00"},
    ]
    out = composer_digest._Out()
    assert composer_digest._left(out, "what do I need to buy", [], _views(notes), set(), date(2026, 10, 11))
    assert not any(LABEL_OPENER.search(line) for line in out.lines), out.lines
    assert out.lines[-1] == "The Camping tent is also still open.", out.lines
