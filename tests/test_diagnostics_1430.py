"""INBOX 1430: the server half of the diagnostics report (core/diagring.py,
api/routes_diag.py). A fixed clock; nothing a person typed reaches the report."""

from __future__ import annotations

import pytest

from tessellate.core import diagring


@pytest.fixture(autouse=True)
def fixed_clock(monkeypatch):
    diagring.clear()
    monkeypatch.setattr(diagring, "clock", lambda: 1_700_000_000.0)
    yield
    diagring.clear()


def test_a_route_loses_its_ids_and_its_query_string():
    assert diagring.route_of("/entries/12/links?q=my secret") == "/entries/:id/links"
    assert diagring.route_of("/files/3f2b9c1e-1111-2222-3333-444455556666") == "/files/:id"
    assert diagring.route_of("/search?q=secret") == "/search"


def test_only_slow_requests_are_kept_and_streams_are_not_slow():
    diagring.note_request("GET", "/entries", 120, 200)
    diagring.note_request("GET", "/chat/stream", 9000, 200)
    diagring.note_request("GET", "/entries/5", 2400, 200)
    diagring.note_request("GET", "/entries/6", 1000, 500)
    rows = diagring.slow_routes()
    assert rows == [{"method": "GET", "route": "/entries/:id", "n": 2, "max_ms": 2400, "status": 500, "avg_ms": 1700}]


def test_a_statement_keeps_its_shape_and_loses_its_literals():
    diagring.note_query("SELECT * FROM entries WHERE title = 'my private plan' AND id = 42", 900)
    diagring.note_query("SELECT 1", 3)
    rows = diagring.slow_queries()
    assert len(rows) == 1
    assert rows[0]["sql"] == "SELECT * FROM entries WHERE title = ? AND id = ?"


def test_an_exception_keeps_frames_not_values_and_repeats_are_counted():
    def boom():
        raise ValueError("bad thing at /home/alice/notes/secret.md")

    for _ in range(3):
        try:
            boom()
        except ValueError as exc:
            diagring.note_exception("/entries/9", exc, "ref1")
    (row,) = diagring.exceptions()
    assert row["n"] == 3 and row["type"] == "ValueError" and row["route"] == "/entries/:id"
    assert "alice" not in row["message"] and "~" in row["message"]
    assert "boom" in row["frames"][-1]


def test_the_buffers_are_bounded():
    for i in range(diagring.KEEP + 50):
        diagring.note_request("GET", f"/r{i}x", 5000, 200)
    assert len(diagring._requests) == diagring.KEEP


def test_a_slow_statement_is_caught_by_the_engine_hook(monkeypatch):
    from sqlalchemy import create_engine, text

    diagring.install_query_hook()
    monkeypatch.setattr(diagring, "SLOW_QUERY_MS", 0)
    engine = create_engine("sqlite://")
    with engine.connect() as conn:
        conn.execute(text("SELECT 'a secret' AS x"))
    assert any(r["sql"] == "SELECT ? AS x" for r in diagring.slow_queries())


def test_the_report_never_carries_a_private_notes_text(client, app_state, monkeypatch):
    marker = "zebra-ledger-7731"
    made = client.post("/entries", json={"content": f"{marker} my private diary", "is_private": True})
    assert made.status_code in (200, 201), made.text
    monkeypatch.setattr(diagring, "SLOW_REQUEST_MS", 0)
    monkeypatch.setattr(diagring, "SLOW_QUERY_MS", 0)
    client.get(f"/entries?q={marker}")
    client.get(f"/search?q={marker}")
    report = client.get("/diagnostics")
    assert report.status_code == 200
    body = report.text
    assert marker not in body and "my private diary" not in body
    assert report.json()["counts"]["notes"] >= 1


def test_a_lag_post_is_stamped_with_the_notebooks_size(client, app_state):
    client.post("/logs/lag", json={"events": [{"kind": "frame", "ms": 300, "view": "notes", "cause": "x"}]})
    row = client.get("/logs/lag").json()[-1]
    assert {"notes", "boards", "docs", "links", "v", "build"} <= set(row)
