"""`/graph?slim=1`: the map's own payload without what every reader assumes.

GRAPH_PLAN "Still open after KG1 to KG9": at 5,000 notes `/graph` was 3.1 MB,
and the first visit after any change spent its time building and encoding
it. Measured on that notebook (`scratchpad/kg1005_graph_bench.py`), a third
of the bytes were values every note carries at its default (a null pin, a
null type, no parent, `false`, `[]`, an unreasoned link's three nulls) and
timestamps to the microsecond. The slim payload leaves those out and the map
(graph.js, `graphFill`) puts them back on arrival, so every reader after the
fetch sees the shape it always did. The dashboard asks for the same slim
payload (its widgets read only each link's two ends), so one cached build
after a change serves both. Without `slim` the payload is unchanged for
every other caller.
"""

from __future__ import annotations

import re
from pathlib import Path

from tessellate.core import deps
from tessellate.core.database import Entry

ROOT = Path(__file__).resolve().parents[1]


def test_slim_leaves_out_the_defaults_and_full_is_unchanged(client):
    a = client.post("/entries", json={"content": "alpha note"}).json()
    b = client.post("/entries", json={"content": "beta note"}).json()
    linked = client.post(f"/entries/{a['id']}/links", json={"target_id": b["id"]})
    assert linked.status_code == 200
    with deps.get_db().session() as session:
        row = session.get(Entry, b["id"])
        row.graph_pin_x, row.graph_pin_y, row.pinned = 1.5, 2.5, True
        session.commit()
    full = client.get("/graph").json()
    slim = client.get("/graph?slim=1").json()
    fa = next(n for n in full["nodes"] if n["id"] == a["id"])
    sa = next(n for n in slim["nodes"] if n["id"] == a["id"])
    sb = next(n for n in slim["nodes"] if n["id"] == b["id"])
    # The full shape keeps every key.
    for key in ("kind", "note_type", "graph_pin_x", "parent_id", "has_file", "pinned", "map_ids", "tags"):
        assert key in fa
    # The slim one leaves out each default, and keeps a value that is set.
    for key in ("kind", "note_type", "graph_pin_x", "graph_pin_y", "parent_id", "has_file", "pinned", "map_ids", "tags"):
        assert key not in sa, key
    assert sb["graph_pin_x"] == 1.5 and sb["pinned"] is True
    # Seconds, still an ISO time with its zone.
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\+00:00", sa["created_at"])
    assert sa["preview"] == fa["preview"] and sa["words"] == fa["words"]
    link = next(e for e in slim["edges"] if e.get("kind") == "link")
    assert "reason" not in link and "link_type" not in link and "reason_confidence" not in link
    full_link = next(e for e in full["edges"] if e.get("kind") == "link")
    assert full_link["reason"] is None and "link_type" in full_link
    assert len(client.get("/graph?slim=1").content) < len(client.get("/graph").content)


def test_the_map_asks_for_it_and_fills_it_back():
    text = (ROOT / "frontend" / "js" / "graph.js").read_text(encoding="utf-8")
    endpoint = text[text.index("function graphEndpoint()") :]
    endpoint = endpoint[: endpoint.index("\n}\n")]
    assert "slim=1" in endpoint
    fill = text[text.index("function graphFill(") :]
    fill = fill[: fill.index("\n}\n")]
    for key in ("note_type", "graph_pin_x", "graph_pin_y", "parent_id", "has_file", "pinned", "map_ids", "tags", "reason", "reason_confidence", "link_type"):
        assert key in fill, key
    canvas = (ROOT / "frontend" / "js" / "graph-canvas.js").read_text(encoding="utf-8")
    assert "apiJson(endpoint).then(graphFill)" in canvas


def test_the_dashboard_shares_the_maps_payload():
    dash = (ROOT / "frontend" / "js" / "dashboard.js").read_text(encoding="utf-8")
    fetch = dash[dash.index("function fetchDashGraph()") :]
    fetch = fetch[: fetch.index("\n}\n")]
    assert 'apiJson("/graph?slim=1"' in fetch
