"""A call the server handed out is signed (L566): a parked card's tool, and
the Undo that comes back from a change. `/chat/tools/execute` runs only what
still matches the tag; changed arguments are refused with a 400 and nothing
runs."""

from __future__ import annotations

from tessellate.ai import consent_store


def _made(client, text="a note to take back"):
    return client.post("/entries", json={"content": text, "category": "General"}).json()["id"]


def test_a_tag_covers_the_name_the_arguments_and_the_steps():
    tag = consent_store.sign_call("delete_note", {"note_id": 1})
    assert consent_store.tag_matches("delete_note", {"note_id": 1}, None, tag)
    assert not consent_store.tag_matches("delete_note", {"note_id": 2}, None, tag)
    assert not consent_store.tag_matches("restore_note", {"note_id": 1}, None, tag)
    assert not consent_store.tag_matches("delete_note", {"note_id": 1}, [{"tool": "x"}], tag)
    assert not consent_store.tag_matches("delete_note", {"note_id": 1}, None, "")


def test_a_parked_tool_is_signed_when_parked():
    key = consent_store.park({"label": "x", "tool": {"name": "delete_note", "arguments": {"note_id": 1}}})
    held = consent_store.peek(key)
    assert consent_store.tag_matches("delete_note", {"note_id": 1}, None, held["tool"]["sig"])


def test_an_undo_with_changed_arguments_is_refused_and_runs_nothing(client):
    mine, other = _made(client, "mine"), _made(client, "somebody else's")
    undo = consent_store.signed({"tool": "delete_note", "arguments": {"note_id": mine}})
    tampered = client.post("/chat/tools/execute", json={"name": "delete_note", "arguments": {"note_id": other}, "sig": undo["sig"]})
    assert tampered.status_code == 400
    assert client.get(f"/entries/{other}").status_code == 200
    honest = client.post("/chat/tools/execute", json={"name": undo["tool"], "arguments": undo["arguments"], "sig": undo["sig"]})
    assert honest.status_code == 200, honest.text
    assert client.get(f"/entries/{mine}").status_code == 404


def test_the_undo_a_press_returns_carries_its_tag(client):
    made = _made(client)
    key = consent_store.park({"label": "Delete", "tool": {"name": "delete_note", "arguments": {"note_id": made}}})
    reply = client.post("/chat/tools/execute", json={"name": "delete_note", "arguments": {"note_id": made}, "consent_id": key})
    assert reply.status_code == 200, reply.text
    undo = reply.json()["undo"]
    assert consent_store.tag_matches(undo["tool"], undo["arguments"], undo.get("steps"), undo["sig"])
