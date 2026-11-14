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


def test_a_call_with_neither_a_card_nor_a_tag_is_refused_and_runs_nothing(client):
    """L-world-class-28: only what the server offered runs; a page cannot make up a call."""
    made = _made(client)
    reply = client.post("/chat/tools/execute", json={"name": "delete_note", "arguments": {"note_id": made}})
    assert reply.status_code == 400 and "not offered" in reply.json()["detail"]
    assert client.get(f"/entries/{made}").status_code == 200


def test_a_change_carries_a_redo_tag_for_the_same_call():
    """The agent's change event signs its own call, so Redo (which runs it again) passes the rule."""
    import inspect

    from tessellate.ai import agent

    assert '"redo_sig": consent_store.sign_call(name, arguments)' in inspect.getsource(agent)


def test_the_redo_button_sends_the_change_s_redo_tag():
    from tests._app_js import app_js_text

    assert "sig: change.redo_sig" in app_js_text()


def test_an_id_with_no_waiting_card_is_refused_at_the_tag_check_and_runs_nothing(client):
    """Review 5899353774 (4): an id alone passed the tag check, so a batch (which
    never reaches the card check) ran on a made-up or spent id."""
    made = _made(client)
    steps = [{"tool": "delete_note", "arguments": {"note_id": made}}]
    made_up = client.post("/chat/tools/execute", json={"name": "batch", "arguments": {}, "steps": steps, "consent_id": "no-such-card"})
    assert made_up.status_code == 409
    key = consent_store.park({"label": "Delete", "tool": {"name": "delete_note", "arguments": {"note_id": made}}})
    consent_store.take(key)
    spent = client.post("/chat/tools/execute", json={"name": "batch", "arguments": {}, "steps": steps, "consent_id": key})
    assert spent.status_code == 409
    assert client.get(f"/entries/{made}").status_code == 200
