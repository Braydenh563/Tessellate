"""The exits of `facts._pair_passes` that `test_night_pairs.py` leaves unpinned.

Characterisation tests written before the function was split by pass (cc-1101):
a budget that runs out in either pass, a pair stored on the later note
whichever order the claims come in, and a question that is skipped because it
is already answered or its pair already known. (A question whose note is gone
is unreachable: the foreign key forbids it, so the guard stays untested.)
"""

from __future__ import annotations

import json
from datetime import timedelta

from sqlalchemy import delete, select

from tessellate.ai import facts
from tessellate.core.database import DerivedFact, Entry, NightRun, utcnow


class Judge:
    def __init__(self) -> None:
        self.asked: list[str] = []

    def chat(self, model, messages):  # noqa: ANN001, ANN201
        system = messages[0]["content"]
        self.asked.append(system)
        if "disagree" in system:
            return {"content": "incompatible - one says 900, the other 950"}
        if "answer the question" in system:
            return {"content": "yes - it names the day"}
        return {"content": ""}


def _note(session, content, days_ago=0):  # noqa: ANN001, ANN201
    entry = Entry(content=content, tags=json.dumps([]))
    entry.created_at = utcnow() - timedelta(days=days_ago)
    session.add(entry)
    session.commit()
    return entry


def _new_night(session):  # noqa: ANN001, ANN201
    """A fresh run that owns every claim and question, with no pair recorded."""
    night = NightRun(trigger="test", budget=10**6, started_at=utcnow())
    session.add(night)
    session.commit()
    session.execute(delete(DerivedFact).where(DerivedFact.kind.in_(("tension", "answered"))))
    for row in session.scalars(select(DerivedFact)).all():
        row.run_id = night.id
    session.commit()
    return night


def _pairs(session, night, *, budget=10**6, provider=None, model=""):  # noqa: ANN001, ANN201
    counts: dict[str, int] = {}
    out = facts._pair_passes(
        session,
        night,
        spent=0,
        budget=budget,
        provider=provider,
        model=model,
        embeddings=None,
        counts=counts,
        models_used=set(),
    )
    return out, counts


def _kind(session, kind):  # noqa: ANN001, ANN201
    return list(session.scalars(select(DerivedFact).where(DerivedFact.kind == kind, DerivedFact.deleted_at.is_(None))))


def _rent_notes(session):  # noqa: ANN001, ANN201
    old = _note(session, "The rent for the flat is 900 pounds a month.", days_ago=30)
    new = _note(session, "The rent for the flat is 950 pounds a month.")
    facts.run(session, budget=5000)
    session.commit()
    return old, new


def _boiler_notes(session):  # noqa: ANN001, ANN201
    _note(session, "When is the boiler service booked for this year?", days_ago=20)
    _note(session, "The boiler service is booked for the fourteenth of March this year.")
    facts.run(session, budget=5000)
    session.commit()


def test_pass_4_stops_on_budget_before_judging_any_claim_pair(session):
    _rent_notes(session)
    night = _new_night(session)
    (spent, derived, stopped), counts = _pairs(session, night, budget=0)
    assert (spent, derived, stopped) == (0, 0, "budget")
    assert _kind(session, "tension") == [] and counts == {}


def test_a_pair_is_stored_on_the_later_note_in_whichever_order_the_claims_come(session):
    # Newer note written to the database first, then the older one, and the
    # reverse: the row lands on the newer note both ways.
    for first_days_ago, second_days_ago in ((30, 0), (0, 30)):
        old_first = first_days_ago > second_days_ago
        a = _note(session, "The rent for the flat is 900 pounds a month.", days_ago=first_days_ago)
        b = _note(session, "The rent for the flat is 950 pounds a month.", days_ago=second_days_ago)
        newer = b if old_first else a
        facts.run(session, budget=5000)
        session.commit()
        night = _new_night(session)
        (_, derived, stopped), counts = _pairs(session, night)
        assert (derived, stopped, counts) == (1, "done", {"tension": 1})
        assert [row.entry_id for row in _kind(session, "tension")] == [newer.id]
        facts.forget(session)
        session.execute(delete(Entry))
        session.commit()


def test_pass_5_stops_on_budget_before_judging_a_question(session):
    _boiler_notes(session)
    night = _new_night(session)
    judge = Judge()
    (spent, derived, stopped), _ = _pairs(session, night, budget=1, provider=judge, model="small")
    assert stopped == "budget" and spent == 0 and derived == 0
    assert not any("answer the question" in asked for asked in judge.asked)
    assert _kind(session, "answered") == []


def test_an_already_answered_question_is_not_judged_again(session):
    _boiler_notes(session)
    night = _new_night(session)
    judge = Judge()
    (_, derived, _), _ = _pairs(session, night, provider=judge, model="small")
    assert derived == 1 and len(_kind(session, "answered")) == 1
    judged = sum("answer the question" in asked for asked in judge.asked)
    # A second night in which every fact is "new" again, the answer still standing.
    again = NightRun(trigger="test", budget=10**6, started_at=utcnow())
    session.add(again)
    session.commit()
    for row in session.scalars(select(DerivedFact).where(DerivedFact.kind.in_(("claim", "question")))).all():
        row.run_id = again.id
    session.commit()
    (_, derived, stopped), _ = _pairs(session, again, provider=judge, model="small")
    assert (derived, stopped) == (0, "done")
    assert sum("answer the question" in asked for asked in judge.asked) == judged


def test_a_dismissed_answer_is_never_judged_again(session):
    _boiler_notes(session)
    night = _new_night(session)
    judge = Judge()
    _pairs(session, night, provider=judge, model="small")
    (row,) = _kind(session, "answered")
    row.deleted_at = utcnow()  # dismissed: a tombstone, which `_known_pairs` still counts
    session.commit()
    judged = sum("answer the question" in asked for asked in judge.asked)
    again = NightRun(trigger="test", budget=10**6, started_at=utcnow())
    session.add(again)
    session.commit()
    for fact in session.scalars(select(DerivedFact).where(DerivedFact.kind.in_(("claim", "question")))).all():
        fact.run_id = again.id
    session.commit()
    (_, derived, _), _ = _pairs(session, again, provider=judge, model="small")
    assert derived == 0 and _kind(session, "answered") == []
    assert sum("answer the question" in asked for asked in judge.asked) == judged
