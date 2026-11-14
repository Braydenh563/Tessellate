"""Dismissed link pairs and accepted neighbourhoods reach the learning loop (L-world-class-85).

The loop was built in KG9 (`ai/learning`, `/learned/corrections`); the plan's
state line said these two were not traced. These tests follow each from the
decision to what the next suggestion pass does, on a fixed clock.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from tessellate.ai import learning
from tessellate.core import database

FIXED_NOW = datetime(2026, 11, 14, 9, 0, 0, tzinfo=timezone.utc)


def _note(client, content, tags=None):
    response = client.post("/entries", json={"content": content, "tags": tags or []})
    assert response.status_code in (200, 201), response.text
    return response.json()


def _pair_in(client, a, b):
    rows = client.get("/entries/link-suggestions").json()
    return next((r for r in rows if {r["source_id"], r["target_id"]} == {a["id"], b["id"]}), None)


def _neighbourhood(client):
    """Two notes with one tag and one shared linked note: offered by `tags` and `neighbours`."""
    hub = _note(client, "Studio year plan")
    a = _note(client, "Glaze trial, cone 6", ["glazelab"])
    b = _note(client, "Thursday firing log", ["glazelab"])
    for note in (a, b):
        client.post(f"/entries/{note['id']}/links", json={"target_id": hub["id"]})
    return a, b


def test_a_dismissed_pair_is_a_correction_and_never_comes_back(client, session):
    a, b = _neighbourhood(client)
    assert _pair_in(client, a, b)
    made = client.post("/learned/corrections", json={"kind": "dismiss_link", "subject": {"a": b["id"], "b": a["id"]}})
    assert made.status_code in (200, 201), made.text
    rows = learning.corrections(session, kind="dismiss_link")
    assert [(r.subject["a"], r.subject["b"]) for r in rows] == [(b["id"], a["id"])]
    assert (min(a["id"], b["id"]), max(a["id"], b["id"])) in learning.boosts(session, kind="links")
    assert _pair_in(client, a, b) is None


def test_the_dismissal_outlives_six_hundred_other_corrections(client, session):
    a, b = _neighbourhood(client)
    client.post("/learned/corrections", json={"kind": "dismiss_link", "subject": {"a": a["id"], "b": b["id"]}})
    for i in range(600):
        learning.record(session, kind="refile", subject={"entry_id": 1}, from_value=f"c{i}", to_value="d")
    session.commit()
    assert _pair_in(client, a, b) is None


def test_accepted_neighbourhoods_lift_the_signals_they_were_offered_for(client, session, monkeypatch):
    monkeypatch.setattr(database, "utcnow", lambda: FIXED_NOW)
    a, b = _neighbourhood(client)
    row = _pair_in(client, a, b)
    assert row
    before = {s["signal"]: s["confidence"] for s in row["signals"]}
    assert {"tags", "neighbours"} <= set(before)
    for i in range(6):
        client.post(
            "/learned/corrections",
            json={"kind": "accept_link", "subject": {"a": 8000 + i, "b": 8100 + i, "signals": ["tags", "neighbours"]}},
        )
    weights = learning.signal_weights(session)
    assert 1.0 < weights["neighbours"] <= learning.SIGNAL_WEIGHT_RANGE[1]
    after = {s["signal"]: s["confidence"] for s in _pair_in(client, a, b)["signals"]}
    assert after["neighbours"] > before["neighbours"]


def test_a_decision_counts_for_half_after_one_half_life(session, monkeypatch):
    monkeypatch.setattr(database, "utcnow", lambda: FIXED_NOW)
    old = learning.record(session, kind="dismiss_link", subject={"a": 1, "b": 2, "signals": ["tags"]})
    session.get(database.AuditLog, old.id).created_at = FIXED_NOW - timedelta(days=learning.HALF_LIFE_DAYS)
    session.commit()
    # one dismissal at half weight: 2 * (0 + 1) / (0 + 0.5 + 2) = 0.8 (at full weight it would be 2/3)
    assert abs(learning.signal_weights(session)["tags"] - 0.8) < 1e-9


def test_forgetting_a_dismissal_offers_the_pair_again_and_restoring_hides_it(client, session):
    a, b = _neighbourhood(client)
    client.post("/learned/corrections", json={"kind": "dismiss_link", "subject": {"a": a["id"], "b": b["id"]}})
    assert _pair_in(client, a, b) is None
    marked = learning.revive_dismissals(session)
    session.commit()
    assert len(marked) == 1
    assert _pair_in(client, a, b)
    assert learning.restore_dismissals(session, marked) == 1
    session.commit()
    assert _pair_in(client, a, b) is None
