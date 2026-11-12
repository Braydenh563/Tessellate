"""Rollups over a live query's table (GRAPH_PLAN, "After KG1 to
KG9": count, sum, min, max, earliest and latest).

The table's footer reads `rollups` from `GET /entries/query`: one block per
column, computed over every note the query matched (not only the 500 rows
the table draws), from the property index (`EntryProperty.number` and
`.date`), so a value that does not read as a number is counted and nothing
else. A private note has no rows in the index and is never in a rollup.
"""

from __future__ import annotations


def _note(client, text):
    return client.post("/entries", json={"content": text}).json()


def _query(client, q):
    response = client.get("/entries/query", params={"q": q})
    assert response.status_code == 200, response.text
    return response.json()


def test_numbers_and_dates_roll_up(client):
    _note(client, "---\ntype: Trip\ncost: 120\nwhen: 2026-03-02\n---\n# Lisbon")
    _note(client, "---\ntype: Trip\ncost: 80.5\nwhen: 2025-11-20\n---\n# Porto")
    _note(client, "---\ntype: Trip\ncost: soon\n---\n# Faro")
    body = _query(client, "type:trip")
    cost = body["rollups"]["cost"]
    assert cost["count"] == 3
    assert cost["sum"] == 200.5
    assert cost["min"] == 80.5
    assert cost["max"] == 120
    when = body["rollups"]["when"]
    assert when["count"] == 2
    assert when["earliest"] == "2025-11-20"
    assert when["latest"] == "2026-03-02"
    # A column with no number has no sum: the footer offers count only.
    assert "sum" not in body["rollups"]["type"]
    assert body["rollups"]["type"]["count"] == 3


def test_a_rollup_covers_every_match_not_only_the_drawn_rows(client, monkeypatch):
    from tessellate.api import routes_entries

    monkeypatch.setattr(routes_entries, "QUERY_ROWS_MAX", 2)
    for cost in (1, 2, 3, 4):
        _note(client, f"---\ntype: Bill\ncost: {cost}\n---\n# Bill {cost}")
    body = _query(client, "type:bill")
    assert len(body["rows"]) == 2
    assert body["rollups"]["cost"]["sum"] == 10
    assert body["rollups"]["cost"]["count"] == 4


def test_a_private_note_is_not_rolled_up(client, session):
    from tessellate.core.database import Entry, EntryProperty

    made = _note(client, "---\ntype: Bill\ncost: 5\n---\n# Open")
    hidden = _note(client, "---\ntype: Bill\ncost: 50\n---\n# Hidden")
    entry = session.get(Entry, hidden["id"])
    entry.is_private = True
    session.query(EntryProperty).filter(EntryProperty.entry_id == hidden["id"]).delete()
    session.commit()
    body = _query(client, "type:bill")
    assert body["ids"] == [made["id"]]
    assert body["rollups"]["cost"]["sum"] == 5


def test_no_terms_no_rollups(client):
    assert _query(client, "")["rollups"] == {}
