"""Decision 68's pass, slice 1: `ai/learned_audit.check` is pure (CHAT_PLAN 67, 68)."""

from __future__ import annotations

from datetime import date, datetime

from tessellate.ai import learned_audit as audit
from tessellate.ai.learned_audit import FactView, NoteView
from tessellate.ai.verdicts import Known, norm

TODAY = date(2026, 11, 1)


def _fact(fid, entry, text, kind="claim", **more):
    return FactView(id=fid, entry_id=entry, kind=kind, text=text, **more)


def _note(nid, content, tags=(), **more):
    return NoteView(id=nid, content=content, tags=tuple(tags), **more)


def _one(rows, notes, known=Known()):
    found = audit.check(rows, {note.id: note for note in notes}, known, TODAY)
    return {item.fact_id: item for item in found}


def _at(note_text, sentence):
    start = note_text.index(sentence)
    return (start, start + len(sentence))


def test_a_note_that_is_gone_retires_what_it_taught():
    row = _fact(1, 7, "I always take the early train to work.")
    assert _one([row], [_note(7, "", gone=True)])[1].code == "note-gone"
    assert _one([row], [])[1].code == "note-gone"


def test_a_note_that_no_longer_says_it_retires_the_row():
    row = _fact(1, 7, "I always take the early train to work.")
    found = _one([row], [_note(7, "I take the bus now, always.")])
    assert found[1].action == audit.RETIRE and found[1].code == "note-edited"


def test_a_row_the_note_still_says_is_left_alone():
    text = "I always take the early train to work."
    assert _one([_fact(1, 7, text)], [_note(7, f"Notes.\n{text}\nMore.")]) == {}


def test_the_persons_own_edit_is_never_judged():
    row = _fact(1, 7, "gone from the note", edited=True)
    assert _one([row], [_note(7, "something else entirely")]) == {}


def test_a_joke_tag_retires_the_claim_with_its_reason():
    text = "I never wash my socks, they are self cleaning."
    for tag in ("joke", "#Jokes", "humour/joke", "Quote", "fiction", "test", "Drafts"):
        found = _one([_fact(1, 7, text)], [_note(7, text, tags=[tag])])
        assert found[1].code == "out-of-context", tag
        assert found[1].action == audit.RETIRE
    assert "tagged joke" in _one([_fact(1, 7, text)], [_note(7, text, tags=["joke"])])[1].reason


def test_other_tags_do_not_count():
    text = "I always take the early train to work."
    assert _one([_fact(1, 7, text)], [_note(7, text, tags=["work", "commute"])]) == {}


def test_a_sentence_inside_a_quote_is_out_of_context():
    content = 'My uncle says "I am the best driver alive and everyone agrees.'
    sentence = "I am the best driver alive and everyone agrees."
    row = _fact(1, 7, sentence, span=_at(content, sentence))
    assert _one([row], [_note(7, content)])[1].code == "out-of-context"
    line = "> I am the best driver alive and everyone agrees."
    row = _fact(1, 7, sentence, span=_at(line, sentence))
    assert _one([row], [_note(7, line)])[1].reason == "The sentence sits inside a quote."


def test_a_line_of_a_question_and_answer_list_is_out_of_context():
    content = "What is a cat?\nA small mammal that always sleeps in the sun.\nWhat is a dog?\nA loyal animal that always barks."
    answer = "A small mammal that always sleeps in the sun."
    row = _fact(1, 7, answer, span=_at(content, answer))
    assert _one([row], [_note(7, content)])[1].reason == "The note is a list of questions and answers."


def test_a_row_marked_wrong_is_retired_but_a_pinned_one_is_not():
    text = "The rent is always paid on the first of the month."
    known = Known(wrong=frozenset({(7, norm(text))}))
    row = _fact(1, 7, text)
    assert _one([row], [_note(7, text)], known)[1].code == "marked-wrong"
    other = _fact(2, 8, text)
    found = _one([other], [_note(8, text)], known)
    assert found[2].reason == "The same words are a sentence you marked wrong."
    pinned = Known(pinned={(7, norm(text)): TODAY})
    assert _one([row], [_note(7, text)], pinned) == {}


def test_the_persons_verdict_rows_are_not_judged():
    row = _fact(1, 7, "gone words that nothing holds", kind="wrong")
    assert _one([row], [_note(7, "x")]) == {}


def test_a_repeat_in_one_note_is_retired_and_in_two_notes_flagged():
    text = "I always keep the receipts for a year."
    note7, note8 = _note(7, text + " " + text), _note(8, text)
    found = _one([_fact(1, 7, text), _fact(2, 7, text), _fact(3, 8, text)], [note7, note8])
    assert 1 not in found
    assert (found[2].action, found[2].code) == (audit.RETIRE, "duplicate")
    assert (found[3].action, found[3].code) == (audit.FLAG, "duplicate")


def test_the_older_of_two_claims_that_disagree_is_flagged():
    old, new = "The rent for the flat is 900 every month.", "The rent for the flat is 950 every month."
    notes = [_note(7, old, written=datetime(2026, 1, 1)), _note(8, new, written=datetime(2026, 6, 1))]
    found = _one([_fact(1, 7, old), _fact(2, 8, new)], notes)
    assert list(found) == [1]
    assert found[1].action == audit.FLAG and found[1].code == "contradiction"
    assert found[1].detail == new
    # And the other way round, by the note's day and not the row's id.
    notes = [_note(7, old, written=datetime(2026, 9, 1)), _note(8, new, written=datetime(2026, 6, 1))]
    assert list(_one([_fact(1, 7, old), _fact(2, 8, new)], notes)) == [2]


def test_claims_about_different_things_do_not_disagree():
    a, b = "I always walk 5 km on Sundays after lunch.", "The boiler is always serviced in 2 weeks."
    assert _one([_fact(1, 7, a), _fact(2, 8, b)], [_note(7, a), _note(8, b)]) == {}


def test_a_date_spoken_of_as_ahead_that_has_passed_is_flagged():
    text = "The passport renewal is due on 3 March 2026 at the office."
    found = _one([_fact(1, 7, text)], [_note(7, text)])
    assert found[1].action == audit.FLAG and found[1].code == "stale-date"
    assert found[1].detail == "2026-03-03"
    assert "3 March 2026" in found[1].reason


def test_dates_in_three_spellings_and_the_not_ahead_cases():
    assert audit.stale_date("The deadline is 2026-01-15 for sure.", TODAY) == date(2026, 1, 15)
    assert audit.stale_date("The deadline is March 3, 2026 for sure.", TODAY) == date(2026, 3, 3)
    assert audit.stale_date("The report will be done by 1st Feb 2026.", TODAY) == date(2026, 2, 1)
    # Still ahead, only just gone (within the grace), no words of looking ahead, not a date.
    assert audit.stale_date("The deadline is 2026-12-15 for sure.", TODAY) is None
    assert audit.stale_date("The deadline was 2026-10-15 for sure.", TODAY) is None
    assert audit.stale_date("I moved house on 3 March 2026 and loved it.", TODAY) is None
    assert audit.stale_date("The deadline is 2026-13-45 somehow.", TODAY) is None


def test_a_pair_whose_side_was_retired_is_retired_with_it():
    text = "I always take the early train to work."
    claim = _fact(1, 7, text)
    kept = _fact(2, 8, "I never take the early train to work.")
    pair = _fact(3, 8, kept.text, kind="tension", sides=(2, 1))
    notes = [_note(7, "I take the bus now."), _note(8, kept.text)]
    found = _one([claim, kept, pair], notes)
    assert found[1].code == "note-edited"
    assert found[3].code == "pair-side-gone" and found[3].action == audit.RETIRE
    alone = _one([kept, _fact(3, 8, kept.text, kind="tension", sides=(2, 9))], [_note(8, kept.text)])
    assert alone[3].code == "pair-side-gone"
    both = _one([claim, kept, pair], [_note(7, text), _note(8, kept.text)])
    assert 3 not in both


def test_retirements_come_before_flags_and_one_finding_per_row():
    text = "The deadline is due on 3 March 2026 for sure."
    rows = [_fact(1, 7, text), _fact(2, 8, "gone")]
    found = audit.check(rows, {7: _note(7, text), 8: _note(8, "x")}, Known(), TODAY)
    assert [(item.fact_id, item.action) for item in found] == [(2, audit.RETIRE), (1, audit.FLAG)]
