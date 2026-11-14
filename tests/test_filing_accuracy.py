"""Filing with no model, measured on a labelled notebook (the 2026-10-10
triage, decision 7; WORLD_CLASS_PLAN 23, decision 8).

`tests/fixtures/filing/notes.json` is 120 hand-labelled notes in twelve
categories a person might keep, ten each, written to overlap the way real
notes do ("Lisbon" is in Travel twice and nowhere else; "book" is in
Reading, Travel and Car; "car insurance" is filed under Money). Each note
has a `kind` (line, pasted, joke, caption, list) and nine carry
`"sensitive": true`. The first forty are the triage's; the other eighty were
written for section 23 before any of its filing code, so they measure it
rather than describe it. Each note is filed leave-one-out, against the other
119; top-1 accuracy counts an abstention as a miss.

Measured (`scratchpad/filing-tools/measure.py`, leave one out, through
`janitor.categorise` with no chat model):

| step | no model | with the embedder (bge-small, no chat model) |
| --- | --- | --- |
| baseline, 2026-10-10 | 0.175 (8 wrong, 91 abstained) | 0.817 (18 wrong, 4 abstained) |
| step 2, the pack replaces the Gemini map | 0.192 (8 wrong) | 0.817 |
| step 3, the decision (decision 2), sensitive held | 0.417 (15 wrong; 0.533 with sensitive filing on) | 0.808 (20 wrong) |
| step 6, the everyday vocabulary (`tests/test_everyday_vocabulary.py`) | 0.617 (11 wrong; 0.792 with sensitive filing on); 48 held-out notes 0.458 to 0.667 | not re-measured |
| Q29, a held sensitive note counts by its suggested category (owner, 2026-11-11) | 0.800 on the bar (0.625 filed outright, 10 wrong); 48 notes 0.833 | not re-measured |
| Q29 re-measure, `janitor.categorise` filed outright, a held note counts as not filed (fastembed bge-small run here, 2026-11-11; the lost `measure.py` was rewritten, see `agent-remaining/gap5-1111.md`) | 120 notes 0.650 (10 wrong, 32 not filed); 48 notes 0.562; 60 notes (C) 0.567 | 120 notes 0.742 (11 wrong, 20 not filed); 48 notes 0.646; 60 notes (C) 0.633 |
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from tessellate.ai import lexical_filing, tagging
from tessellate.entry import manager

NOTES = json.loads((Path(__file__).parent / "fixtures" / "filing" / "notes.json").read_text(encoding="utf-8"))
#: The floor this file holds: no step may file fewer right, and of the notes
#: it files at least this share must be right (a wrong category is a note
#: lost; the module's promise since INBOX 434 is "right 80% of the times it
#: files"). Sensitive notes held back (decision 6) count as not filed.
FLOOR_TOP1 = 0.60
FLOOR_PRECISION = 0.75
#: Decision 8, as the owner moved it on 2026-11-11 (HANDOVER decision 6, OPEN
#: row 260): below this top-1 with no model, the step fails. 0.6, filed
#: outright (a sensitive note held for the person counts as not filed); the
#: model path keeps 0.8.
BAR_TOP1 = 0.6
#: The ranker's own score, a held note counted by the category it suggests
#: (Q29, 2026-11-11): kept at its old height as a guard on the ranking.
SUGGESTED_TOP1 = 0.8


def _seed(session) -> list[int]:
    ids = [manager.create_entry(session, note["content"], category_name=note["category"]).id for note in NOTES]
    session.commit()
    return ids


def _score(session, ids: list[int]) -> tuple[float, int, set[str]]:
    """(top-1 accuracy, notes filed wrong, the names filed into)."""
    right = wrong = 0
    names: set[str] = set()
    for entry_id, note in zip(ids, NOTES):
        match = lexical_filing.lexical_category(session, note["content"], exclude_entry_id=entry_id)
        if match:
            names.add(match.name)
            right += match.name == note["category"]
            wrong += match.name != note["category"]
    return right / len(NOTES), wrong, names


def test_the_fixture_is_120_notes_in_twelve_categories_of_every_kind() -> None:
    assert len(NOTES) == 120
    assert set(Counter(note["category"] for note in NOTES).values()) == {10}
    assert {note["kind"] for note in NOTES} == {"line", "pasted", "joke", "caption", "list"}
    assert sum(1 for note in NOTES if note.get("sensitive")) >= 6


def test_filing_with_no_model_holds_its_floor(session) -> None:
    ids = _seed(session)
    right, wrong, names = _score(session, ids)
    assert right >= FLOOR_TOP1, right
    filed_right = right * len(NOTES)
    assert filed_right / (filed_right + wrong) >= FLOOR_PRECISION, (right, wrong)
    #: Never a category the notebook does not have ("Fitness" for a Gym
    #: note, "Literature & Travel"): the Gemini weights filed 14 of 40 so.
    assert names <= {note["category"] for note in NOTES}, names


def _suggested_score(session, ids: list[int]) -> float:
    """Top-1 where a sensitive note held back for the person (decision 6)
    counts by the category it suggests, the chip they see, as the owner
    decided on 2026-11-11 (Q29); an abstention is still a miss."""
    right = 0
    for entry_id, note in zip(ids, NOTES):
        decision = lexical_filing.decide(session, note["content"], exclude_entry_id=entry_id)
        pick = decision.filed or (decision.ranked[0] if decision.held and decision.ranked else None)
        right += bool(pick) and pick.name == note["category"]
    return right / len(NOTES)


def test_filing_with_no_model_reaches_the_bar(session) -> None:
    """Decision 8's bar, 0.6 top-1 with no model (the owner, 2026-11-11):
    measured honestly, filed outright, a note held back for the person
    counted as not filed. The precision floor above guards wrong filings."""
    ids = _seed(session)
    right, _wrong, _names = _score(session, ids)
    assert right >= BAR_TOP1, right


def test_the_ranker_still_puts_the_right_category_first(session) -> None:
    """Q29 (the owner, 2026-11-11): counted by the category a held note
    suggests, the ranker reaches 0.8. A guard on the ranking, not the bar."""
    ids = _seed(session)
    assert _suggested_score(session, ids) >= SUGGESTED_TOP1


def test_tags_offered_are_only_the_notebooks_own(session) -> None:
    """INBOX, the owner 2026-10-10: "Study and university tags are suggested
    on the top note if it has no tags no matter what the note is about".
    With no model, a note is offered only tags the notebook already uses and
    only those its words or its nearest notes back: a note about cooking in a
    notebook whose most used tags are "study" and "university" gets neither,
    and a note that says "study" outright gets no tag the notebook lacks."""
    for i in range(6):
        manager.create_entry(session, f"Lecture {i} notes on thermodynamics and entropy", category_name="Uni", tags=["study", "university"])
    for i in range(2):
        manager.create_entry(session, f"Pasta night {i}: garlic, chilli, lemon", category_name="Cooking", tags=["dinner"])
    session.commit()
    cooking = tagging.suggest(session, "Lentil dal with cumin and a tin of tomatoes", have=[])
    assert not {"study", "university"} & set(cooking), cooking
    vocabulary = {"study", "university", "dinner"}
    for text in ("Study plan for the exam: two hours a day at the university library", "A squat and deadlift session"):
        assert set(tagging.suggest(session, text, have=[])) <= vocabulary
