"""Dates, entities and duplicates are fact kinds the night pass reads by rule (L657)."""

from __future__ import annotations

from sqlalchemy import select

from tessellate.ai import facts, facts_kinds, learned_audit_run
from tessellate.core.database import DerivedFact, Entity, EntityMention

NOTE = "Meet Priya Raman at the studio on 12 March 2027 to sign the lease."


def _entry(client, content: str) -> dict:
    return client.post("/entries", json={"content": content}).json()


def _kinds(session) -> list[tuple[str, int]]:
    return sorted((row.kind, row.entry_id) for row in session.scalars(select(DerivedFact)))


def test_the_kinds_are_listed_and_the_audit_judges_only_the_original_four():
    assert {"date", "entity", "duplicate"} <= set(facts.KINDS)
    assert facts.JUDGED_KINDS == ("claim", "question", "tension", "answered")
    assert set(facts_kinds.EXACT_KINDS) == {"date", "entity", "duplicate"}


def test_a_date_a_note_names_is_a_fact_with_its_span(ai_client, fake_ollama, session):
    note = _entry(ai_client, NOTE)
    ai_client.post("/night/run", json={"budget": 2000, "force": True})
    rows = [r for r in session.scalars(select(DerivedFact)) if r.kind == "date"]
    assert rows and all(r.entry_id == note["id"] and NOTE[r.span_start:r.span_end] == r.text for r in rows), rows
    assert "12 March" in rows[0].text


def test_an_entity_the_note_mentions_is_a_fact_where_it_names_it(ai_client, fake_ollama, session):
    note = _entry(ai_client, NOTE)
    entity = Entity(name="Priya Raman")
    session.add(entity)
    session.flush()
    session.add(EntityMention(entity_id=entity.id, entry_id=note["id"]))
    session.commit()
    ai_client.post("/night/run", json={"budget": 2000, "force": True})
    rows = [r for r in session.scalars(select(DerivedFact)) if r.kind == "entity"]
    assert [(r.text, NOTE[r.span_start:r.span_end]) for r in rows] == [("Priya Raman", "Priya Raman")]


def test_a_note_that_repeats_another_word_for_word_is_marked_a_duplicate_of_the_first(ai_client, fake_ollama, session):
    first = _entry(ai_client, NOTE)
    second = _entry(ai_client, NOTE)
    ai_client.post("/night/run", json={"budget": 4000, "force": True})
    rows = [r for r in session.scalars(select(DerivedFact)) if r.kind == "duplicate"]
    assert [(r.entry_id, r.text) for r in rows] == [(second["id"], f"Says the same as note {first['id']}")]


def test_the_learned_store_check_leaves_exact_facts_alone(ai_client, fake_ollama, session):
    _entry(ai_client, NOTE)
    _entry(ai_client, NOTE)
    ai_client.post("/night/run", json={"budget": 4000, "force": True})
    exact = {r.id for r in session.scalars(select(DerivedFact)) if r.kind in facts_kinds.EXACT_KINDS}
    assert exact
    rows, _notes = learned_audit_run.load(session)
    assert not exact & {row.id for row in rows}
