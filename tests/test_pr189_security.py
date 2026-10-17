"""Security and robustness review of PR 189 (CodeQL-style): inputs that used to
end in a 500, a poisoned stored value or a slow regex."""

from __future__ import annotations

import json
import time


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


def _said(client, question: str) -> str:
    sent = client.post("/chat/stream", json={"question": question})
    assert sent.status_code == 200, sent.text[:200]
    events = [json.loads(line) for line in sent.text.splitlines() if line.strip()]
    return " ".join(str(e.get("delta") or "") for e in events if e.get("type") == "answer")


def test_a_slash_count_that_is_not_an_ascii_number_does_not_crash(client):
    client.post("/entries", json={"content": "Golf on Sunday"})
    assert "newest note" in _said(client, "/recent ²")
    assert "oldest note" in _said(client, "/oldest " + "9" * 5000)
    assert "newest note" in _said(client, "/recent 99999999999999999999")


def test_slash_find_reads_a_few_words_and_none_as_a_pattern(client):
    client.post("/entries", json={"content": "Golf on Sunday"})
    client.post("/entries", json={"content": "Dentist on Monday"})
    many = _said(client, "/find " + " ".join(f"word{i}" for i in range(1200)))
    assert many.startswith("No note holds")
    # "_" and "%" are LIKE wildcards: they match themselves only.
    assert _said(client, "/find __").startswith("No note holds")
    assert "No note is tagged #%" in _said(client, "/count %")


def _seconds(call) -> float:
    started = time.perf_counter()
    call()
    return time.perf_counter() - started


def test_open_checkbox_scan_is_linear_in_blank_lines():
    # Before: 20,000 whitespace lines took 5.1 s (each line start read on to the end).
    from tessellate.ai import slash_more

    note = "[ ]\n" + " \n" * 20000 + "- [ ] call the dentist"
    found = []
    assert _seconds(lambda: found.extend(slash_more._OPEN_BOX.findall(note))) < 0.5
    assert found == ["call the dentist"]
    assert slash_more._OPEN_BOX.findall("  * [ ] \tbuy milk\n- [x] done") == ["buy milk"]


def test_proofread_modal_lookup_is_linear_in_a_long_word():
    # Before: 40,000 letters then a slip took 12 s, the 20,000 case 3 s.
    from tessellate.ai import proofread

    line = "x" * 30000 + " we shoud"
    assert _seconds(lambda: proofread._modal("shoud", line)) < 1.0
    assert proofread._modal("shoud", "we shoud prepare") == "should"
    assert proofread._modal("shoud", "shoud prepare") == ""


def test_a_number_too_big_for_a_duration_is_not_a_crash(client):
    assert _said(client, "/made last 99999999999999999999 days")
    assert _said(client, "what did I write in the last 99999999999999999999 days")
