"""Ask for the mind map, timeline and sequence kinds (L-documents-27): a flat list of blocks in, short checked ops out.

The same contract as `diagram_ask` (a rule reads the words with no model; the model writes ops when it runs; every op is
played on a copy and kept only when it applies), in the lazy sibling `diagram_ask_kinds`. Provider tests use the fake
transport: real-model output is unverified.
"""

from __future__ import annotations

import json

from tessellate.ai import diagram_ask_kinds as dak

MIND = {"nodes": [
    {"uid": "u1", "type": "r", "text": "Plan"},
    {"uid": "u2", "type": "b", "text": "Budget", "parent": "u1"},
    {"uid": "u3", "type": "b", "text": "Hiring", "parent": "u1"},
    {"uid": "u4", "type": "b", "text": "Salaries", "parent": "u2"},
]}
TIME = {"nodes": [
    {"uid": "u1", "type": "s", "text": "Launch"},
    {"uid": "u2", "type": "p", "text": "2030", "parent": "u1"},
    {"uid": "u3", "type": "e", "text": "Beta", "parent": "u2"},
    {"uid": "u4", "type": "p", "text": "2031"},
]}
SEQ = {"nodes": [
    {"uid": "u1", "type": "a", "text": "Alice", "id": "Alice"},
    {"uid": "u2", "type": "a", "text": "Bob", "id": "Bob"},
    {"uid": "u3", "type": "m", "text": "Hello", "from": "Alice", "to": "Bob"},
]}


def test_mind_map_add_rename_move_delete_by_rule():
    assert dak.by_rule("mindmap", "add Rent under Budget", MIND)["ops"] == [{"op": "add", "type": "b", "text": "Rent", "parent": "u2"}]
    assert dak.by_rule("mindmap", "rename Hiring to Recruiting", MIND)["ops"] == [{"op": "rename", "target": "u3", "text": "Recruiting"}]
    assert dak.by_rule("mindmap", "move Salaries under Hiring", MIND)["ops"] == [{"op": "move", "target": "u4", "parent": "u3"}]
    assert dak.by_rule("mindmap", "delete Budget", MIND)["ops"] == [{"op": "delete", "target": "u2"}]


def test_a_branch_cannot_move_into_itself_and_the_root_stays():
    out = dak.by_rule("mindmap", "move Budget under Salaries", MIND)
    assert out["ops"] == [] and out["dropped"] == 1
    assert dak.by_rule("mindmap", "delete Plan", MIND)["ops"] == []


def test_timeline_adds_a_section_a_period_and_an_event():
    assert dak.by_rule("timeline", "add section Growth", TIME)["ops"] == [{"op": "add", "type": "s", "text": "Growth", "parent": ""}]
    assert dak.by_rule("timeline", "add period 2032 to Launch", TIME)["ops"] == [{"op": "add", "type": "p", "text": "2032", "parent": "u1"}]
    assert dak.by_rule("timeline", "add event GA to 2030", TIME)["ops"] == [{"op": "add", "type": "e", "text": "GA", "parent": "u2"}]
    assert dak.by_rule("timeline", "add event GA to Launch", TIME)["ops"] == []


def test_sequence_adds_a_participant_and_a_message():
    assert dak.by_rule("sequence", "add participant Carol", SEQ)["ops"] == [{"op": "add", "type": "a", "text": "Carol"}]
    out = dak.by_rule("sequence", "add message Thanks from Bob to Alice", SEQ)["ops"]
    assert out == [{"op": "add", "type": "m", "text": "Thanks", "from": "Bob", "to": "Alice"}]
    assert dak.by_rule("sequence", "add message Hi from Bob to Zed", SEQ)["ops"] == []


def test_deleting_a_participant_takes_its_messages_and_two_clauses_play_in_order():
    out = dak.by_rule("sequence", "add participant Carol; then add message Hi from Alice to Carol", SEQ)
    assert [o["type"] for o in out["ops"]] == ["a", "m"]
    assert dak.by_rule("sequence", "delete Bob", SEQ)["ops"] == [{"op": "delete", "target": "u2"}]


def test_an_unread_ask_says_so_and_an_unknown_kind_reads_nothing():
    assert dak.by_rule("mindmap", "make it prettier", MIND)["said"] == dak.NOT_READ
    assert dak.by_rule("flowchart", "add x", MIND)["ops"] == []


def test_checked_drops_hostile_ops_and_cuts_words():
    hostile = [
        {"op": "drop table"}, "x", {"op": "add", "type": "b", "text": "y" * 500, "parent": "Budget"},
        {"op": "delete", "target": "u1"}, {"op": "add", "type": "b", "text": "z", "parent": "Ghost"},
    ]
    kept, dropped = dak.checked("mindmap", hostile, MIND)
    assert kept == [{"op": "add", "type": "b", "text": "y" * dak.TEXT_CHARS, "parent": "u2"}] and dropped == 4
    many, extra = dak.checked("mindmap", [{"op": "add", "type": "b", "text": f"S{i}", "parent": "u1"} for i in range(30)], MIND)
    assert len(many) == dak.MAX_OPS and extra == 30 - dak.MAX_OPS


def test_the_prompt_is_budgeted_and_the_blocks_are_lines():
    for kind in ("mindmap", "timeline", "sequence"):
        assert len(dak.prompt(kind)) <= 700
    lines = dak.described(MIND)
    assert "u4: Salaries (b) in u2" in lines
    big = {"nodes": [{"uid": f"u{i}", "type": "b", "text": "word " * 20} for i in range(120)]}
    assert len(dak.described(big)) <= dak.DESCRIBED_CHARS


# --- the route ----------------------------------------------------------------------------------


def test_the_route_answers_a_kind_by_rule_with_no_model(client):
    body = client.post("/drafts/diagram-ask", json={"ask": "rename Hiring to Recruiting", "kind": "mindmap", "kind_model": MIND}).json()
    assert body["by"] == "rule" and body["ops"] == [{"op": "rename", "target": "u3", "text": "Recruiting"}]


def test_the_route_asks_the_model_for_a_kind_and_checks_its_ops(ai_client, fake_ollama):
    fake_ollama.librarian_reply = json.dumps({"ops": [
        {"op": "add", "type": "m", "text": "Bye", "from": "Bob", "to": "Alice"},
        {"op": "delete", "target": "Ghost"},
    ]})
    body = ai_client.post("/drafts/diagram-ask", json={"ask": "Bob says bye", "kind": "sequence", "kind_model": SEQ}).json()
    assert body["by"] == "model" and body["dropped"] == 1
    assert body["ops"] == [{"op": "add", "type": "m", "text": "Bye", "from": "Bob", "to": "Alice"}]
    sent = fake_ollama.chat_calls[-1]
    assert sent[0]["content"] == dak.prompt("sequence") and "u3: Hello (m) Alice -> Bob" in sent[-1]["content"]


def test_a_model_reply_with_nothing_usable_falls_back_to_the_rule_for_a_kind(ai_client, fake_ollama):
    fake_ollama.librarian_reply = "I would rename it."
    body = ai_client.post("/drafts/diagram-ask", json={"ask": "rename Hiring to Recruiting", "kind": "mindmap", "kind_model": MIND}).json()
    assert body["by"] == "rule" and "rule" in body["said"]


def test_the_route_caps_a_kind_model_and_refuses_a_bad_kind(client):
    many = {"nodes": [{"uid": f"u{i}", "type": "b", "text": "a"} for i in range(121)]}
    codes = [
        client.post("/drafts/diagram-ask", json=body).status_code
        for body in (
            {"ask": "add x", "kind": "mindmap", "kind_model": many},
            {"ask": "add x", "kind": "pie", "kind_model": MIND},
        )
    ]
    assert codes == [422, 422]
