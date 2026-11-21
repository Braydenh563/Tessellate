"""The I7 gate's filing eval (LEDGER L-world-class-87): filing accuracy rises 10 points after
20 synthetic corrections.

Protocol, on the 67-note set of `tests/fixtures/tagging/notes.json` (`tests/_tag_eval.py`) and the
model-free lexical filer (`lexical_filing.decide`, which learns through `personal_lexicon`):
each note is filed leave-one-out; the first 20 notes it could not file become 20 synthetic
refile corrections (the person putting each in its labelled category, with the note's text as the
excerpt); accuracy is read before and after on the 47 notes that were not taught, so a correction
can only help by generalising, never by remembering its own note.

After L-world-class-650 (a taught topic weighs by how specific it is to the category, among the
corrections and every note's own words): 40 of 47 (85%) after, minus 6 points. Only 4 held-out
notes were missed before, so plus 10 (5 notes) is out of reach on this set whatever the loop does.
Measured first, 2026-11-21, fixed clock not needed (no dates): held-out accuracy 43 of 47 (91%) before,
37 of 47 (79%) after: minus 12 points. The corrections teach the lexicon that topics shared by
several categories belong to the category taught most ("Ideas"), which takes notes from "Uni"
out of the confident band. The gate's bar is plus 10, so the gate test below is a strict xfail:
it flips to a pass, and the marker must go, when the loop gains what it promises. A real model
(embedding filing, `janitor._semantic_category`) was not run: this is the lexical filer only.
"""

from __future__ import annotations

import pytest

from tests import _tag_eval

TAUGHT = 20
GATE_POINTS = 10


def _filed_right(session, ids: list[int], notes: list[int]) -> int:
    from tessellate.ai import lexical_filing

    right = 0
    for i in notes:
        decision = lexical_filing.decide(session, _tag_eval.body(_tag_eval.NOTES[i]), exclude_entry_id=ids[i])
        got = decision.filed.name if decision.filed and not decision.held else None
        right += got == _tag_eval.NOTES[i]["category"]
    return right


def _gain(session) -> tuple[int, int, int]:
    """(held-out notes, right before, right after) twenty corrections."""
    from tessellate.ai import learning, lexical_filing

    ids = _tag_eval.seed(session)
    every = list(range(len(ids)))
    missed = [i for i in every if _filed_right(session, ids, [i]) == 0 and lexical_filing.decide(
        session, _tag_eval.body(_tag_eval.NOTES[i]), exclude_entry_id=ids[i]).filed is None]
    taught = missed[:TAUGHT]
    held = [i for i in every if i not in taught]
    before = _filed_right(session, ids, held)
    for i in taught:
        learning.record(
            session, kind="refile", subject={"entry_id": ids[i]}, from_value="Uncategorised",
            to_value=_tag_eval.NOTES[i]["category"], excerpt=_tag_eval.NOTES[i]["content"],
        )
    session.commit()
    return len(held), before, _filed_right(session, ids, held)


def test_twenty_corrections_are_measured_on_notes_they_did_not_teach(session):
    held, before, after = _gain(session)
    print(f"\nFILING EVAL: {before}/{held} ({round(100 * before / held)}%) -> {after}/{held} ({round(100 * after / held)}%)")
    assert held == len(_tag_eval.NOTES) - TAUGHT
    assert before == 43, "the baseline moved: re-measure before trusting the gate below"


@pytest.mark.xfail(strict=True, reason="measured minus 12 points (91% to 79%) on 2026-11-21; LEDGER L-world-class-87")
def test_the_loop_gains_ten_points_after_twenty_corrections(session):
    held, before, after = _gain(session)
    assert 100 * (after - before) / held >= GATE_POINTS
