"""Audit 1028 E43: Confirm runs what its card proposed and spends the card.

`/chat/tools/execute` used to run whatever name and arguments the page sent
and merely spent the id. A press now has to match the parked card; an Undo
(no card id) runs only with the tag the server handed out (L-world-class-28)."""

from tessellate.ai import consent_store
from tests._tool_sig import call


def _card(name, arguments):
    return consent_store.park({"label": "x", "tool": {"name": name, "arguments": arguments}})


def _notes(client):
    return [n["content"] for n in client.get("/entries?limit=50").json()]


def test_a_press_runs_the_card_once(client):
    args = {"content": "Pressed once"}
    key = _card("create_note", args)
    first = client.post("/chat/tools/execute", json={"name": "create_note", "arguments": args, "consent_id": key})
    again = client.post("/chat/tools/execute", json={"name": "create_note", "arguments": args, "consent_id": key})
    assert first.status_code == 200
    assert again.status_code == 409 and "no longer waiting" in again.json()["detail"]
    assert _notes(client).count("Pressed once") == 1


def test_a_press_cannot_spend_a_card_on_another_action(client):
    key = _card("create_note", {"content": "Proposed"})
    other_args = client.post(
        "/chat/tools/execute", json={"name": "create_note", "arguments": {"content": "Swapped"}, "consent_id": key}
    )
    assert other_args.status_code == 409 and "different action" in other_args.json()["detail"]
    other_tool = client.post(
        "/chat/tools/execute", json={"name": "count_notes", "arguments": {}, "consent_id": _card("create_note", {"content": "p"})}
    )
    assert other_tool.status_code == 409
    assert "Swapped" not in _notes(client)


def test_an_unknown_card_runs_nothing_and_no_card_still_undoes(client):
    unknown = client.post("/chat/tools/execute", json={"name": "create_note", "arguments": {"content": "Ghost"}, "consent_id": "nope"})
    assert unknown.status_code == 409
    #: Neither a card nor a tag: a call the page made up, refused (L-world-class-28).
    unsigned = client.post("/chat/tools/execute", json={"name": "create_note", "arguments": {"content": "Made up"}})
    assert unsigned.status_code == 400 and "not offered" in unsigned.json()["detail"]
    undo = client.post("/chat/tools/execute", json=call("create_note", {"content": "Undo path"}))
    assert undo.status_code == 200
    assert _notes(client) == ["Undo path"]
