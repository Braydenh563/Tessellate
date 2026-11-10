"""The Ask box in the diagram builder (dgai-1110, DOCUMENTS_PLAN "Placed from INBOX, 2026-11-10"; the format is
docs/roadmap/agent-remaining/dgai-1110.md F1 to F5).

The owner: "the ai should be able to help you make it and make changes and suggest edits". An ask comes back as
operations on the D1 model, the same five verbs by rule (no model) and from the model; every op is played on a copy
and kept only when it applies. Provider tests run against the fake transport: real-model output is unverified.
"""

from __future__ import annotations

import json

from tessellate.ai import diagram_ask

SHOP = {
    "nodes": [
        {"id": "A", "text": "Order placed", "shape": "stadium", "group": None},
        {"id": "B", "text": "In stock?", "shape": "diamond", "group": "G1"},
        {"id": "C", "text": "Ship it", "shape": "rect", "group": "G1"},
    ],
    "edges": [{"from": "A", "to": "B", "label": ""}, {"from": "B", "to": "C", "label": "Yes"}],
    "subgraphs": [{"id": "G1", "title": "Warehouse", "parent": None}],
}


def test_add_a_step_after_a_decision_takes_the_rest_as_the_arrows_words():
    out = diagram_ask.by_rule("add a refund step after In stock? No", SHOP)
    assert out["ops"] == [{"op": "add", "text": "Refund", "shape": "rect", "after": "B", "label": "No", "group": "G1"}]
    assert out["dropped"] == 0


def test_rename_a_group_by_its_words():
    out = diagram_ask.by_rule("rename Warehouse to Fulfilment", SHOP)
    assert out["ops"] == [{"op": "rename", "target": "G1", "text": "Fulfilment"}]


def test_join_nest_delete_and_two_clauses():
    out = diagram_ask.by_rule("connect Order placed to Ship it with skip; then delete In stock?", SHOP)
    assert out["ops"] == [
        {"op": "join", "from": "A", "to": "C", "label": "skip"},
        {"op": "delete", "target": "B"},
    ]
    nest = diagram_ask.by_rule("move Order placed into Warehouse", SHOP)["ops"]
    assert nest == [{"op": "nest", "target": "A", "group": "G1"}]
    lift = diagram_ask.by_rule("take Ship it out of its group", SHOP)["ops"]
    assert lift == [{"op": "nest", "target": "C", "group": ""}]
    arrow = diagram_ask.by_rule("remove the arrow from In stock? to Ship it", SHOP)["ops"]
    assert arrow == [{"op": "delete", "from": "B", "to": "C"}]


def test_between_replaces_the_arrow_and_a_later_op_names_the_new_block():
    out = diagram_ask.by_rule("add Pack between In stock? and Ship it, then rename Pack to Pack the box", SHOP)
    assert out["ops"] == [
        {"op": "add", "text": "Pack", "shape": "rect", "after": "B", "label": "Yes", "group": "G1"},
        {"op": "join", "from": "Pack", "to": "C", "label": ""},
        {"op": "delete", "from": "B", "to": "C"},
        {"op": "rename", "target": "Pack", "text": "Pack the box"},
    ]


def test_a_question_is_a_decision_and_a_group_can_be_added():
    out = diagram_ask.by_rule("add Paid? after Order placed", SHOP)
    assert out["ops"][0]["shape"] == "diamond"
    group = diagram_ask.by_rule("add a group called Customer", SHOP)["ops"]
    assert group == [{"op": "add", "text": "Customer", "shape": "group", "after": "", "label": "", "group": ""}]


def test_words_it_cannot_read_say_so_and_change_nothing():
    out = diagram_ask.by_rule("make it prettier", SHOP)
    assert out["ops"] == [] and out["said"]
    missing = diagram_ask.by_rule("rename Nowhere to Somewhere", SHOP)
    assert missing["ops"] == [] and missing["dropped"] == 1


def test_untrusted_ops_are_checked_against_the_model():
    hostile = [
        {"op": "eval", "code": "alert(1)"},
        {"op": "add", "text": "x" * 500, "shape": "<script>", "after": "Ship it"},
        {"op": "rename", "target": "Nobody", "text": "Hi"},
        {"op": "rename", "target": "C", "text": "   "},
        {"op": "join", "from": "A", "to": "A"},
        {"op": "nest", "target": "G1", "group": "G1"},
        "not a dict",
        {"op": "delete", "target": "A"},
        {"op": "join", "from": "A", "to": "B"},
    ]
    kept, dropped = diagram_ask.checked(hostile, SHOP)
    assert kept[0] == {"op": "add", "text": "x" * diagram_ask.TEXT_CHARS, "shape": "rect", "after": "C", "label": "", "group": "G1"}
    assert kept[1] == {"op": "delete", "target": "A"}
    #: A is gone by then, so the last join cannot apply.
    assert len(kept) == 2 and dropped == 7
    many, extra = diagram_ask.checked([{"op": "add", "text": f"S{i}"} for i in range(30)], SHOP)
    assert len(many) == diagram_ask.MAX_OPS and extra == 30 - diagram_ask.MAX_OPS


def test_the_block_limit_holds():
    full = {"nodes": [{"id": f"N{i}", "text": f"S{i}", "shape": "rect", "group": None} for i in range(120)], "edges": [], "subgraphs": []}
    kept, dropped = diagram_ask.checked([{"op": "add", "text": "One more"}], full)
    assert kept == [] and dropped == 1


def test_the_prompt_is_budgeted_and_the_diagram_is_lines():
    assert len(diagram_ask.ASK_PROMPT) <= 700
    lines = diagram_ask.described(SHOP)
    assert "B: In stock? [diamond] in Warehouse" in lines and "B -> C: Yes" in lines
    big = {"nodes": [{"id": f"N{i}", "text": "word " * 20, "shape": "rect", "group": None} for i in range(120)], "edges": [], "subgraphs": []}
    assert len(diagram_ask.described(big)) <= diagram_ask.DESCRIBED_CHARS


def test_the_model_reply_is_read_as_json_only():
    reply = 'Sure: {"ops": [{"op": "rename", "target": "Warehouse", "text": "Fulfilment"}]} done'
    assert diagram_ask.read_reply(reply) == [{"op": "rename", "target": "Warehouse", "text": "Fulfilment"}]
    assert diagram_ask.read_reply("[1, 2]") == [1, 2]
    assert diagram_ask.read_reply("no json here") == []
    assert diagram_ask.read_reply('{"ops": "nope"}') == []


# --- the route ----------------------------------------------------------------------------------


def test_the_route_answers_by_rule_with_no_model(client):
    body = client.post("/drafts/diagram-ask", json={"ask": "rename Warehouse to Fulfilment", "model": SHOP}).json()
    assert body["by"] == "rule" and body["ops"] == [{"op": "rename", "target": "G1", "text": "Fulfilment"}]


def test_the_route_asks_the_model_and_checks_its_ops(ai_client, fake_ollama):
    fake_ollama.librarian_reply = json.dumps({"ops": [
        {"op": "add", "text": "Refund", "shape": "rect", "after": "In stock?", "label": "No"},
        {"op": "delete", "target": "Ghost"},
    ]})
    body = ai_client.post("/drafts/diagram-ask", json={"ask": "add a refund when it is out of stock", "model": SHOP}).json()
    assert body["by"] == "model" and body["dropped"] == 1
    assert body["ops"] == [{"op": "add", "text": "Refund", "shape": "rect", "after": "B", "label": "No", "group": "G1"}]
    sent = fake_ollama.chat_calls[-1]
    assert sent[0]["content"] == diagram_ask.ASK_PROMPT
    assert "B: In stock? [diamond] in Warehouse" in sent[-1]["content"]


def test_a_model_reply_with_nothing_usable_falls_back_to_the_rule(ai_client, fake_ollama):
    fake_ollama.librarian_reply = "I would rename it."
    body = ai_client.post("/drafts/diagram-ask", json={"ask": "rename Warehouse to Fulfilment", "model": SHOP}).json()
    assert body["by"] == "rule" and body["ops"] == [{"op": "rename", "target": "G1", "text": "Fulfilment"}]
    assert "rule" in body["said"]


def test_the_route_caps_what_it_is_sent(client):
    many = {"nodes": [{"id": f"N{i}", "text": "a", "shape": "rect"} for i in range(121)]}
    codes = [
        client.post("/drafts/diagram-ask", json=body).status_code
        for body in ({"ask": "x" * 301, "model": SHOP}, {"ask": " ", "model": SHOP}, {"ask": "add x", "model": many})
    ]
    assert codes == [422, 400, 422]
