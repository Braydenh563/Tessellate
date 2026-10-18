"""How a no-model answer reads (INBOX 1301 D5).

The owner: "the responses for how they are written, how they sound, how they
are formatted and everything are very poor and might have even gotten
worse". Ask's answer to "What have I saved about social connections?" was a
guide note said as every fragment it holds glued with ";" ("not cheesy:;",
"Follow- Up Questions:;", quoted ice breakers in a row), then its "Phase 1:
..." lines as notes of their own ("Your first Phase note has the Opener"),
under "You asked: <question>", closing on a reminder made of the guide's
advice. Gold item 22 is that notebook; `_gold.form` is the measure.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from tests import _gold
from tests.test_gold_answers import FIXTURE, TODAY, _answer, _notebook
from tessellate.ai import composer_digest, insights

ROOT = Path(__file__).resolve().parents[1]
ITEM = next(a for a in FIXTURE["answers"] if a["n"] == 22)
QUESTION = ITEM["question"]


def _social(content_edit=None) -> dict:  # noqa: ANN001
    notes = _notebook(ITEM)
    if content_edit:
        notes = [dict(n, content=content_edit(n["content"])) if n["id"] == 100 else n for n in notes]
    return composer_digest.answer(QUESTION, notes, today=TODAY)


def test_a_guide_note_is_two_clean_sentences_with_no_glued_fragments():
    text = _social()["text"]
    guide = next(p for p in text.split("\n\n") if "Social Skills Guide" in p)
    assert len(re.findall(r"[.?!](?:\s|$)", guide)) <= 2, guide
    assert ";" not in text
    #: The quoted examples are the guide's material, never said as prose.
    assert "spice" not in guide and '"' not in guide
    assert not re.search(r"cheesy:|Questions:", text)


def test_a_notes_sections_are_said_as_its_shape_not_as_notes():
    text = _social()["text"]
    assert "It's in four phases: the Opener, the Connection, the Ask and the Follow-Up." in text
    assert "Phase note" not in text


def test_markdown_section_headings_are_said_as_the_shape_too():
    text = _social(lambda c: c.replace("\nPhase ", "\n## Phase "))["text"]
    assert "It's in four phases: the Opener, the Connection, the Ask and the Follow-Up." in text
    assert "Phase note" not in text and ";" not in text


def test_a_numbered_heading_said_twice_is_one_lecture_not_sections():
    """Gold 1: "Psych lecture 1: ..." labels both sentences of one note."""
    item = next(a for a in FIXTURE["answers"] if a["n"] == 1)
    text = _answer(item)["text"]
    assert "In your first psych lecture" in text and "It's in" not in text


def test_the_lead_names_the_category_as_typed():
    assert _social()["text"].split("\n\n")[0] == "You have five notes about social connections, 22 July to 4 October."


def test_a_reminder_is_offered_only_for_a_stated_task():
    assert _social()["offer"]["label"] == "Remind you to text Daniel about the 25th?"
    #: With no open task left, the guide's advice is still not a reminder.
    notes = [n for n in _notebook(ITEM) if n["id"] != 104]
    offer = (composer_digest.answer(QUESTION, notes, today=TODAY) or {}).get("offer") or {}
    assert "follow-up questions" not in str(offer.get("label", ""))


def test_a_habit_is_reported_in_one_tense():
    text = _social()["text"]
    assert "you interrupt when you're nervous, and you told yourself to count to two before answering" in text


def test_another_persons_plan_is_not_the_writers_drift():
    notes = [{"id": 1, "content": "Met Daniel at the gym. He wants to try the outdoor crag in November.", "created_at": "2026-08-01"}]
    assert insights.drift(notes, date(2026, 10, 11)) == []
    mine = [{"id": 1, "content": "I want to learn Spanish this year.", "created_at": "2026-08-01"}]
    assert insights.drift(mine, date(2026, 10, 11))


def test_the_gold_set_reads_clean():
    """Measured 2026-10-18 over the 22 gold answers: before, the longest
    sentence 134 words, 27 ";" joins, one answer with 15 broken patterns;
    after, 35, 1 and none."""
    forms = [_gold.form(_answer(a)["text"]) for a in FIXTURE["answers"]]
    assert max(f["max_words"] for f in forms) <= 40
    assert sum(f["semicolons"] for f in forms) <= 1
    assert not [f for f in forms if f["broken"]]


def test_ask_does_not_echo_the_question_above_its_answer():
    """The question stays in the box it was typed in; "You asked:" above the
    answer said it twice."""
    assert 'id="asked-question"' not in (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    assert "You asked: " not in (ROOT / "frontend/js/capture-ask.js").read_text(encoding="utf-8")
