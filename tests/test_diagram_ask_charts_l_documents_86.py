"""The Ask box and Suggestions for Gantt, pie, state, class and ER blocks (L-documents-86).

Backend: `diagram_ask_kinds` reads each kind by rule and checks a model's ops (fake transport; real inference is not
exercised here). Client: diagram-ai-kinds.js flattens the blocks and plays the ops on a copy with the kind's own
functions; diagram-ai.js offers the removals a person would make by hand. The backend produces the ops the client
plays, so both halves are held to one format.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from tessellate.ai import diagram_ask_kinds as dak

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"


def _region(path: Path, name: str) -> str:
    text = path.read_text(encoding="utf-8")
    return text[text.index(f"// {name}-BEGIN") : text.index(f"// {name}-END")]


def _node(kind: str, source: str, steps: str):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    code = "\n".join([
        _region(JS / "documents-mermaid.js", "DIAGRAM-MODEL"),
        _region(JS / "diagram-ops.js", "DIAGRAM-OPS"),
        _region(JS / "diagram-kinds.js", "DIAGRAM-KINDS"),
        _region(JS / "diagram-kinds-more.js", "DIAGRAM-KINDS-MORE"),
        "Object.assign(diagramKinds, diagramKindsMore);",
        _region(JS / "diagram-ai-kinds.js", "DIAGRAM-AI-KINDS"),
        _region(JS / "diagram-ai.js", "DIAGRAM-AI"),
        f"const A = diagramKinds.{kind}; const ko = diagramKindOps; const m = A.parse({json.dumps(source)});",
        f"const result = (() => {{ {steps} }})();",
        "console.log(JSON.stringify({ result }));",
    ])
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as handle:
        handle.write(code)
    try:
        out = subprocess.run([node, handle.name], capture_output=True, text=True, timeout=60, check=True)
    finally:
        Path(handle.name).unlink(missing_ok=True)
    return json.loads(out.stdout)["result"]


def _play(kind: str, source: str, ask: str) -> dict:
    blocks = _node(kind, source, "return dakFlatten(A, ko, m);")
    reply = dak.by_rule(kind, ask, {"nodes": blocks})
    out = _node(kind, source, f"const r = dakApply(A, ko, m, {json.dumps(reply['ops'])}); return {{ r, printed: A.print(m), again: Boolean(A.parse(A.print(m))) }};")
    return {"reply": reply, **out}


GANTT = "gantt\n    title Plan\n    section Build\n    Code :a1, 2026-01-05, 5d\n    section Ship\n    Release :after a1, 2d\n"
PIE = 'pie title Pets\n    "Dogs" : 40\n    "Cats" : 25\n'
STATE = "stateDiagram-v2\n    state Idle\n    state Busy\n    Idle --> Busy : go\n"
CLASS = "classDiagram\n    class Order\n    class Customer\n    Order --> Customer\n"
ER = 'erDiagram\n    ORDER {\n        int id\n    }\n    CUSTOMER\n    CUSTOMER ||--o{ ORDER : places\n'


def test_each_kind_reads_its_adds_by_rule_and_plays_them_as_blocks():
    cases = {
        "gantt": (GANTT, "add section QA; add task Test under QA", ["Test :3d"]),
        "pie": (PIE, "add slice Birds at 12.5", ['"Birds" : 12.5']),
        "state": (STATE, "add state Done; add transition from Busy to Done called finish; add transition from Done to end", ["state Done", "Busy --> Done : finish", "Done --> [*]"]),
        "class": (CLASS, "add class Invoice; add member +total: int to Invoice; add relation from Invoice to Order called bills", ["class Invoice {", "+total: int", "Invoice --> Order : bills"]),
        "er": (ER, "add entity Invoice; add attribute int total to Invoice; add relationship from INVOICE to ORDER called covers", ["Invoice {", "int total", "Invoice ||--o{ ORDER : covers"]),
    }
    for kind, (source, ask, wants) in cases.items():
        got = _play(kind, source, ask)
        assert got["r"]["done"] == len(got["reply"]["ops"]) > 0, (kind, got)
        assert got["again"], kind
        for want in wants:
            assert want in got["printed"], (kind, want, got["printed"])


def test_set_rename_move_and_delete_play_on_the_five_kinds():
    assert 'Dogs" : 55' in _play("pie", PIE, "set Dogs to 55")["printed"]
    assert "Code :a1, 2026-01-05, 9d" in _play("gantt", GANTT, "set Code to a1, 2026-01-05, 9d")["printed"]
    moved = _play("gantt", GANTT, "move Release under Build")["printed"]
    assert moved.index("Release") < moved.index("section Ship")
    assert 'Hounds" : 40' in _play("pie", PIE, "rename Dogs to Hounds")["printed"]
    gone = _play("state", STATE, "delete Busy")["printed"]
    assert "Busy" not in gone and "Idle --> " not in gone
    assert "Customer" not in _play("class", CLASS, "delete Customer")["printed"]


def test_the_backend_drops_what_does_not_apply():
    blocks = _node("pie", PIE, "return dakFlatten(A, ko, m);")
    model = {"nodes": blocks}
    assert dak.by_rule("pie", "add slice Fish at 0", model)["ops"] == []
    assert dak.by_rule("pie", "set Dogs to lots", model)["ops"] == []
    assert dak.by_rule("pie", "set Ghost to 5", model)["ops"] == []
    kept, dropped = dak.checked("pie", [{"op": "add", "type": "s", "text": "n", "parent": "Ghost"}, {"op": "set", "target": "Cats", "value": "9"}], model)
    assert [o["op"] for o in kept] == ["set"] and dropped == 1
    state = {"nodes": _node("state", STATE, "return dakFlatten(A, ko, m);")}
    assert dak.by_rule("state", "add transition from Idle to Nowhere", state)["ops"] == []
    assert dak.by_rule("class", "add member +x to Ghost", {"nodes": _node("class", CLASS, "return dakFlatten(A, ko, m);")})["ops"] == []


def test_the_prompts_are_budgeted_and_the_blocks_are_lines():
    for kind in ("gantt", "pie", "state", "class", "er"):
        assert len(dak.prompt(kind)) <= 700, kind
    lines = dak.described({"nodes": _node("state", STATE, "return dakFlatten(A, ko, m);")})
    assert "Idle (s) id Idle" not in lines and "(x)" in lines


def test_the_route_asks_the_model_for_a_chart_kind_and_checks_its_ops(ai_client, fake_ollama):
    blocks = _node("pie", PIE, "return dakFlatten(A, ko, m);")
    fake_ollama.librarian_reply = json.dumps({"ops": [{"op": "add", "type": "s", "text": "Birds", "value": "7"}, {"op": "delete", "target": "Ghost"}]})
    body = ai_client.post("/drafts/diagram-ask", json={"ask": "add birds", "kind": "pie", "kind_model": {"nodes": blocks}}).json()
    assert body["by"] == "model" and body["dropped"] == 1
    assert body["ops"] == [{"op": "add", "type": "s", "text": "Birds", "value": "7"}]
    assert fake_ollama.chat_calls[-1][0]["content"] == dak.prompt("pie")


def test_the_route_answers_a_chart_kind_by_rule_with_no_model(client):
    blocks = _node("pie", PIE, "return dakFlatten(A, ko, m);")
    body = client.post("/drafts/diagram-ask", json={"ask": "set Cats to 31", "kind": "pie", "kind_model": {"nodes": blocks}}).json()
    assert body["by"] == "rule" and body["ops"][0]["op"] == "set"


def test_suggestions_find_what_a_person_would_remove_and_drop_it():
    got = _node("pie", 'pie\n    "A" : 1\n    "a" : 2\n', "const rows = diagramAiPure.kindLint('pie', m); return [rows.map((r) => r.text), A.print(diagramAiPure.kindDrop(m, rows[0].drop))];")
    assert got[0] == ["a is on the pie twice."] and '"a"' not in got[1] and '"A"' in got[1]
    gantt = _node("gantt", "gantt\n    title A\n    title B\n    section Empty\n    section Full\n    T :1d\n", "const rows = diagramAiPure.kindLint('gantt', m); return [rows.map((r) => r.text), rows.map((r) => A.print(diagramAiPure.kindDrop(m, r.drop)))];")
    assert gantt[0] == ["The section Empty has no tasks.", "The chart has a second title."]
    assert "section Empty" not in gantt[1][0] and gantt[1][1].count("title") == 1
    state = _node("state", "stateDiagram-v2\n    state Lonely\n    state Group {\n    }\n    A --> B\n    A --> B\n", "return diagramAiPure.kindLint('state', m).map((r) => r.text);")
    assert state == ["A goes to B twice.", "The group Group holds nothing.", "Lonely has no transitions."] or sorted(state) == sorted(["A goes to B twice.", "The group Group holds nothing.", "Lonely has no transitions."])
    cls = _node("class", "classDiagram\n    class A\n    class B\n    class C {\n      +x\n    }\n    A --> B\n    A --> B\n", "return diagramAiPure.kindLint('class', m).map((r) => r.text);")
    assert cls == ["A and B are joined twice."]
    er = _node("er", "erDiagram\n    LONE\n    A ||--o{ B : x\n", "return diagramAiPure.kindLint('er', m).map((r) => r.text);")
    assert er == ["LONE stands alone."]


def test_the_ask_box_and_suggestions_are_wired_for_every_kind():
    ai = (JS / "diagram-ai.js").read_text(encoding="utf-8")
    assert "kinds.MORE.test" not in ai and "have neither yet" not in ai
    for kind in ("gantt", "pie", "state", "class", "er"):
        assert f"{kind}: \"add " in ai, kind


def test_the_placeholder_example_for_a_slice_is_read():
    model = {"nodes": _node("pie", PIE, "return dakFlatten(A, ko, m);")}
    assert dak.by_rule("pie", "add slice Cats 30", model)["ops"][0]["value"] == "30"
    assert dak.by_rule("pie", "add slice Birds", model)["ops"][0].get("value") in (None, "10")
