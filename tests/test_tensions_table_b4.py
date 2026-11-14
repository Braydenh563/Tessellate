"""The derived tensions table (WORLD_CLASS_PLAN B4, row 18).

Before this, a scan's findings lived only in the response that carried them:
the Tensions widget could count accepted pairs and nothing else. Now every
finding is an event, and `tensions` is a view rebuilt from three sources kept
elsewhere: the tension events (found, accepted, dismissed), the night shift's
tension facts and the `contradicts` links. The B4 gate: a rebuild from
nothing gives the same rows, and every row cites its source event.
"""

from __future__ import annotations

import json
from datetime import timedelta

from sqlalchemy import select

from tessellate.ai import facts, tensions
from tessellate.core.database import AuditLog, DerivedTension, Entry, EntryLink, utcnow


def _note(client, session, text, days_ago):
    made = client.post("/entries", json={"content": text}).json()
    entry = session.get(Entry, made["id"])
    entry.created_at = utcnow() - timedelta(days=days_ago)
    session.commit()
    return entry


def _snapshot(session):
    return [
        {k: v for k, v in row.items() if k != "computed_at"} | {"at": str(row["computed_at"])}
        for row in tensions.derive(session)
    ]


def _fixture(client, session):
    """Four pairs, one per source and state: a scan finding unresolved, a scan
    finding dismissed, a night finding, and a link made by hand."""
    a = _note(client, session, "The launch is in May.", 90)
    b = _note(client, session, "The launch slipped to August.", 10)
    c = _note(client, session, "Tea is better than coffee.", 80)
    d = _note(client, session, "Coffee beats tea, every time.", 5)
    e = _note(client, session, "The rent for the flat is 900 pounds a month.", 60)
    f = _note(client, session, "The rent for the flat is 950 pounds a month.", 1)
    g = _note(client, session, "Remote work suits the team.", 70)
    h = _note(client, session, "The team works best in the office.", 2)
    tensions.record_event(session, tensions.FOUND, a.id, b.id, reason="May against August", model="fake", confidence=0.7)
    tensions.record_event(session, tensions.FOUND, c.id, d.id, reason="tea against coffee", model="fake", confidence=0.7)
    session.commit()
    client.post("/entries/tensions/dismiss", json={"earlier_id": c.id, "later_id": d.id})
    facts.run(session, budget=5000)
    session.commit()
    client.post(f"/entries/{g.id}/links", json={"target_id": h.id, "link_type": "contradicts"})
    return a, b, c, d, e, f, g, h


def test_each_source_lands_as_one_row_in_its_state(client, session):
    a, b, c, d, e, f, g, h = _fixture(client, session)
    tensions.rebuild(session)
    session.commit()
    rows = {r.pair: r for r in session.scalars(select(DerivedTension))}
    assert rows[tensions.pair_key(a.id, b.id)].status == "open"
    assert rows[tensions.pair_key(a.id, b.id)].reason == "May against August"
    assert rows[tensions.pair_key(a.id, b.id)].model == "fake"
    assert (rows[tensions.pair_key(a.id, b.id)].earlier_id, rows[tensions.pair_key(a.id, b.id)].later_id) == (a.id, b.id)
    assert rows[tensions.pair_key(c.id, d.id)].status == "dismissed"
    night = rows[tensions.pair_key(e.id, f.id)]
    assert night.source == "night" and night.status == "open" and night.model == "local"
    assert (night.earlier_id, night.later_id) == (e.id, f.id)
    linked = rows[tensions.pair_key(g.id, h.id)]
    assert linked.source == "link" and linked.status == "accepted" and linked.model == "person"


def test_a_rebuild_from_nothing_is_deterministic(client, session):
    _fixture(client, session)
    first = _snapshot(session)
    tensions.rebuild(session)
    session.commit()
    session.query(DerivedTension).delete()
    session.commit()
    tensions.rebuild(session)
    session.commit()
    second = _snapshot(session)
    assert first == second
    stored = [
        {k: getattr(r, k) for k in ("pair", "earlier_id", "later_id", "status", "reason", "model", "source", "source_id", "event_id")}
        for r in session.scalars(select(DerivedTension).order_by(DerivedTension.pair))
    ]
    derived = sorted(
        ({k: r[k] for k in ("pair", "earlier_id", "later_id", "status", "reason", "model", "source", "source_id", "event_id")} for r in first),
        key=lambda r: r["pair"],
    )
    assert stored == derived


def test_every_row_cites_its_source_event(client, session):
    _fixture(client, session)
    tensions.rebuild(session)
    session.commit()
    rows = list(session.scalars(select(DerivedTension)))
    assert len(rows) == 4
    for row in rows:
        assert row.event_id is not None, row.pair
        event = session.get(AuditLog, row.event_id)
        assert event is not None
        if row.source == "scan":
            assert event.action == tensions.FOUND and event.payload["pair"] == row.pair
        elif row.source == "link":
            assert event.action == "linked" and event.payload["after"]["link_id"] == row.source_id
        else:
            assert event.entity_id == row.later_id and event.created_at <= row.computed_at


def test_accepting_links_and_the_table_follows(client, session):
    a, b, *_ = _fixture(client, session)
    client.post("/entries/tensions/accept", json={"earlier_id": a.id, "later_id": b.id})
    body = client.get("/entries/tensions/known", params={"status": "accepted"}).json()
    assert tensions.pair_key(a.id, b.id) in {t["key"] for t in body["tensions"]}
    assert body["counts"]["accepted"] == 2
    # Taking the link away is a change of mind: the pair is not offered again.
    link = session.scalars(select(EntryLink).where(EntryLink.link_type == "contradicts", EntryLink.source_entry_id == a.id)).first()
    client.delete(f"/entries/{a.id}/links/{link.id}")
    body = client.get("/entries/tensions/known", params={"status": "open"}).json()
    assert tensions.pair_key(a.id, b.id) not in {t["key"] for t in body["tensions"]}


def test_the_listing_shows_what_a_person_may_open(client, session):
    a, b, _c, _d, e, f, *_ = _fixture(client, session)
    body = client.get("/entries/tensions/known").json()
    keys = {t["key"] for t in body["tensions"]}
    assert keys == {tensions.pair_key(a.id, b.id), tensions.pair_key(e.id, f.id)}
    first = next(t for t in body["tensions"] if t["key"] == tensions.pair_key(a.id, b.id))
    assert first["explanation"] == "May against August"
    assert first["model"] == "fake" and first["computed_at"]
    assert "launch" in first["earlier_excerpt"].lower()
    session.get(Entry, b.id).is_private = True
    session.commit()
    keys = {t["key"] for t in client.get("/entries/tensions/known").json()["tensions"]}
    assert keys == {tensions.pair_key(e.id, f.id)}


def test_a_scan_records_what_it_found_and_never_asks_twice(client, session, monkeypatch):
    from tessellate.api import routes_entries_relations
    from tessellate.core import deps

    a = _note(client, session, "The launch is in May.", 90)
    b = _note(client, session, "The launch slipped to August.", 10)
    monkeypatch.setattr(deps.get_ollama(), "is_running", lambda: True)
    monkeypatch.setattr(deps.get_embeddings(), "is_ready", lambda: True)
    monkeypatch.setattr(routes_entries_relations.search_engine, "cached_similar_pairs", lambda *a_, **k: [(a.id, b.id, 0.8)])
    asked = []

    def judge(earlier, later, models, ollama):
        asked.append((earlier.id, later.id))
        return tensions.Tension(earlier.id, later.id, "May against August", "", "", None, None, 80)

    monkeypatch.setattr(tensions, "compare_pair", judge)
    found = client.get("/entries/tensions").json()
    assert [t["key"] for t in found["tensions"]] == [tensions.pair_key(a.id, b.id)]
    event = session.scalars(select(AuditLog).where(AuditLog.action == tensions.FOUND)).one()
    assert json.loads(json.dumps(event.payload))["reason"] == "May against August"
    again = client.get("/entries/tensions").json()
    assert again["tensions"] == [] and len(asked) == 1
    known = client.get("/entries/tensions/known").json()
    assert [t["key"] for t in known["tensions"]] == [tensions.pair_key(a.id, b.id)]


def test_forgetting_what_was_derived_takes_the_findings_and_keeps_the_links(client, session):
    _a, _b, _c, _d, _e, _f, g, h = _fixture(client, session)
    facts.forget(session)
    session.commit()
    body = client.get("/entries/tensions/known", params={"status": "all"}).json()
    assert [t["key"] for t in body["tensions"]] == [tensions.pair_key(g.id, h.id)]
