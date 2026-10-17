"""Security and robustness review of PR 189 (CodeQL-style): inputs that used to
end in a 500, a poisoned stored value or a slow regex."""

from __future__ import annotations

import json


def test_a_pin_id_that_is_not_an_ascii_number_is_a_404_not_a_500(client):
    # `str.isdigit` is true for "²" and "٣", which `int` then refuses.
    for bad in ("²", "document:²", "٣", "9" * 30, "document:" + "9" * 5000):
        sent = client.put(f"/graph/pin/{bad}", json={"x": 1, "y": 2})
        assert sent.status_code == 404, (bad[:12], sent.status_code)
    many = client.put("/graph/pins", json={"pins": [{"id": "²", "x": 1, "y": 1}, {"id": "9" * 30, "x": 1, "y": 1}, {"id": "document:" + "9" * 5000, "x": 1, "y": 1}]})
    assert many.status_code == 200, many.text
    assert many.json() == {"pinned": 0}


def test_a_pin_cannot_hold_a_value_the_graph_cannot_send(client):
    # JSON the standard library accepts but the response encoder refuses.
    note = client.post("/entries", json={"content": "A note to pin"}).json()
    for raw in ('{"x": Infinity, "y": 1}', '{"x": 1, "y": -Infinity}'):
        sent = client.put(f"/graph/pin/{note['id']}", content=raw, headers={"content-type": "application/json"})
        assert sent.status_code == 422, (raw, sent.status_code)
    body = json.dumps({"pins": [{"id": note["id"], "x": 1, "y": 1}]}).replace("1,", "Infinity,", 1)
    sent = client.put("/graph/pins", content=body, headers={"content-type": "application/json"})
    assert sent.status_code == 422
    assert client.get("/graph").status_code == 200
