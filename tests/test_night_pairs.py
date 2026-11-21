"""The night shift's passes 4 and 5 (WORLD_CLASS_PLAN I1, H1; row 5).

Pass 4: each claim found this run against the nearest claims of other notes;
a pair the model calls incompatible (or, with no model, two near-identical
claims that differ in a number or a "not") is a `tension`. Pass 5: each open
question against the nearest claims written later in other notes; one the
model says answers it (or, with no model, that holds most of what it asks) is
`answered`. Both are stored on the later side with the other in `payload`,
both are deduplicated by pair (tombstones included), and a run with nothing
new spends nothing on them.
"""

from __future__ import annotations

import json
from datetime import timedelta

from sqlalchemy import func, select

from tessellate.ai import facts
from tessellate.core.database import DerivedFact, Entry, utcnow
import pytest
from tests._clock import SUITE_NOW, pin_clock


@pytest.fixture(autouse=True)
def _suite_clock(monkeypatch):
    """Data here is built from SUITE_NOW, and the app reads the same pinned clock."""
    pin_clock(monkeypatch, SUITE_NOW)


def _note(session, content, days_ago=0):
    entry = Entry(content=content, tags=json.dumps([]))
    entry.created_at = utcnow() - timedelta(days=days_ago)
    session.add(entry)
    session.commit()
    return entry


def _kind(session, kind):
    return list(
        session.scalars(select(DerivedFact).where(DerivedFact.kind == kind, DerivedFact.deleted_at.is_(None)))
    )


class Judge:
    """A provider that judges pairs by a rule and counts what it was asked."""

    def __init__(self, tension="incompatible - one says 900, the other 950", answer="yes - it names the day"):
        self.tension = tension
        self.answer = answer
        self.asked: list[str] = []

    def chat(self, model, messages):
        system = messages[0]["content"]
        self.asked.append(system[:20])
        if "disagree" in system:
            return {"content": self.tension}
        if "answer the question" in system:
            return {"content": self.answer}
        return {"content": ""}  # the narrowing step: keep everything


def test_without_a_model_a_changed_number_is_a_tension(session):
    old = _note(session, "The rent for the flat is 900 pounds a month.", days_ago=30)
    new = _note(session, "The rent for the flat is 950 pounds a month.")
    result = facts.run(session, budget=5000)
    session.commit()
    tensions = _kind(session, "tension")
    assert len(tensions) == 1, result
    row = tensions[0]
    assert row.entry_id == new.id  # stored on the later side
    assert new.content[row.span_start : row.span_end] == row.text
    payload = json.loads(row.payload)
    assert payload["other_entry_id"] == old.id
    assert "900" in payload["other_text"]
    assert row.model == "local"
    pair = facts.as_json(row)["pair"]
    assert pair["entry_id"] == old.id and pair["reason"]


def test_without_a_model_unrelated_claims_are_no_tension(session):
    _note(session, "The rent for the flat is 900 pounds a month.", days_ago=30)
    _note(session, "The garden shed needs a new roof before winter.")
    facts.run(session, budget=5000)
    assert _kind(session, "tension") == []


def test_the_model_decides_when_there_is_one(session):
    _note(session, "The launch should happen on the fourth of May.", days_ago=10)
    _note(session, "The launch should happen on the ninth of May.")
    judge = Judge(tension="compatible - both can be true")
    facts.run(session, budget=50_000, provider=judge, model="small")
    assert _kind(session, "tension") == []
    assert any(asked.startswith("Two sentences") for asked in judge.asked)

    facts.forget(session)
    session.commit()
    judge = Judge()
    facts.run(session, budget=50_000, provider=judge, model="small", force=True)
    tensions = _kind(session, "tension")
    assert len(tensions) == 1
    assert tensions[0].model == "small"
    assert json.loads(tensions[0].payload)["reason"] == "one says 900, the other 950"


def test_a_later_claim_answers_an_open_question(session):
    question = _note(session, "When is the boiler service booked for this year?", days_ago=20)
    answer = _note(session, "The boiler service is booked for the fourteenth of March this year.")
    facts.run(session, budget=5000)
    answered = _kind(session, "answered")
    assert len(answered) == 1
    row = answered[0]
    assert row.entry_id == answer.id
    payload = json.loads(row.payload)
    assert payload["other_entry_id"] == question.id
    assert payload["other_text"].endswith("?")


def test_an_earlier_claim_does_not_answer_a_later_question(session):
    _note(session, "The boiler service is booked for the fourteenth of March this year.", days_ago=20)
    _note(session, "When is the boiler service booked for this year?")
    facts.run(session, budget=5000)
    assert _kind(session, "answered") == []


def test_a_second_run_with_nothing_new_spends_nothing_on_pairs(session):
    _note(session, "The rent for the flat is 900 pounds a month.", days_ago=30)
    _note(session, "The rent for the flat is 950 pounds a month.")
    facts.run(session, budget=5000)
    session.commit()
    before = session.scalar(select(func.count(DerivedFact.id)))
    again = facts.run(session, budget=5000)
    assert again["tokens_spent"] == 0
    assert again["derived"] == 0
    assert session.scalar(select(func.count(DerivedFact.id))) == before


def test_a_dismissed_tension_is_never_found_again(session):
    _note(session, "The rent for the flat is 900 pounds a month.", days_ago=30)
    _note(session, "The rent for the flat is 950 pounds a month.")
    facts.run(session, budget=5000)
    session.commit()
    (row,) = _kind(session, "tension")
    facts.remove(session, row)
    session.commit()
    facts.run(session, budget=5000, force=True)
    assert _kind(session, "tension") == []


def test_the_card_counts_the_new_kinds(client, session):
    _note(session, "The rent for the flat is 900 pounds a month.", days_ago=30)
    _note(session, "The rent for the flat is 950 pounds a month.")
    client.post("/night/run", json={"budget": 5000})
    card = client.get("/night/latest").json()
    assert card["counts"].get("tension") == 1
    sample = card["samples"]["tension"][0]
    assert sample["pair"]["text"].startswith("The rent for the flat is 900")


def test_nothing_in_entries_changes(session):
    a = _note(session, "The rent for the flat is 900 pounds a month.", days_ago=30)
    b = _note(session, "The rent for the flat is 950 pounds a month.")
    before = [(e.id, e.content, e.updated_at) for e in session.scalars(select(Entry).order_by(Entry.id))]
    facts.run(session, budget=5000)
    session.commit()
    after = [(e.id, e.content, e.updated_at) for e in session.scalars(select(Entry).order_by(Entry.id))]
    assert before == after and {a.id, b.id} <= {row[0] for row in after}


class _Words:
    """A bag-of-words embedder that counts digits as words, so the same
    sentence again scores 1.0 and one with another number a little less,
    as a real model does."""

    def is_ready(self):
        return True

    def embed_text(self, text):
        import numpy as np

        vector = np.zeros(64, dtype="float32")
        for word in text.lower().replace(".", " ").split():
            vector[sum(map(ord, word)) % 64] += 1.0
        return vector


def test_identical_claims_do_not_crowd_out_the_one_that_disagrees(session):
    """By meaning, four notes saying "950" are each other's nearest at 1.0
    and used to fill every neighbour place, so the older 900 was never
    compared (nightpairs.js, measured on the sweep's fifth seeding)."""
    _note(session, "The rent for the flat is 900 pounds a month.", days_ago=30)
    facts.run(session, budget=50_000, embeddings=_Words())
    session.commit()
    for days in (4, 3, 2, 1):
        _note(session, "The rent for the flat is 950 pounds a month.", days_ago=days)
    facts.run(session, budget=50_000, embeddings=_Words())
    assert len(_kind(session, "tension")) >= 1


class _Prefs:
    """The two methods the switches read, over a dict."""

    def __init__(self, **stored):
        self.stored = {facts._pref_key(name): value for name, value in stored.items()}

    def get_preference(self, key, default=None):
        return self.stored.get(key, default)


def test_the_open_questions_switch_stops_collecting_and_answering(session):
    _note(session, "Who is coming to the garden party on Saturday?", days_ago=30)
    _note(session, "The caterer is coming to the garden party on Saturday.")
    off = _Prefs(open_questions=False)
    facts.run(session, budget=5000, config=off)
    session.commit()
    assert _kind(session, "question") == []
    assert _kind(session, "answered") == []
    assert _kind(session, "claim"), "the claims are still read with questions off"


def test_the_open_questions_switch_on_still_collects_and_answers(session):
    _note(session, "Who is coming to the garden party on Saturday?", days_ago=30)
    _note(session, "The caterer is coming to the garden party on Saturday.")
    facts.run(session, budget=5000, config=_Prefs())
    session.commit()
    assert len(_kind(session, "question")) == 1
