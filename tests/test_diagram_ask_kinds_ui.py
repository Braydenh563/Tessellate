"""Source text: the behaviour is front-end script that pytest cannot run without a browser, so these pin the code's text.

The Ask box for a mind map, timeline and sequence diagram (L-documents-35).

diagram-ai-kinds.js flattens the kind's model, and plays the backend's ops (`diagram_ask_kinds`) on a copy with the
kind's own functions. The backend's ops are produced here by the backend itself, so both halves are held to one format.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from tessellate.ai import diagram_ask_kinds

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"


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
        _region(JS / "diagram-ai-kinds.js", "DIAGRAM-AI-KINDS"),
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


def _flat(kind: str, source: str) -> list[dict]:
    return _node(kind, source, "return dakFlatten(A, ko, m);")


def _play(kind: str, source: str, ask: str) -> dict:
    blocks = _flat(kind, source)
    reply = diagram_ask_kinds.by_rule(kind, ask, {"nodes": blocks})
    out = _node(kind, source, f"const r = dakApply(A, ko, m, {json.dumps(reply['ops'])}); return {{ r, printed: A.print(m) }};")
    return {"reply": reply, **out}


MM = "mindmap\n  root((Plan))\n    Budget\n      Salaries\n    Hiring\n"
TL = "timeline\n  title History\n  section Early\n    2004 : Facebook\n"
SEQ = "sequenceDiagram\n  participant Shop\n  participant Bank\n  Shop->>Bank: hi\n  Note over Shop: n\n"


def test_flatten_gives_the_backends_fields_and_skips_notes():
    mm = _flat("mindmap", MM)
    assert [(n["type"], n["text"], n.get("parent") is not None) for n in mm] == [("r", "Plan", False), ("b", "Budget", True), ("b", "Salaries", True), ("b", "Hiring", True)]
    seq = _flat("sequence", SEQ)
    assert [n["type"] for n in seq] == ["a", "a", "m"]
    assert seq[0]["id"] == "Shop" and (seq[2]["from"], seq[2]["to"]) == ("Shop", "Bank")
    tl = _flat("timeline", TL)
    assert [(n["type"], n["text"]) for n in tl] == [("s", "Early"), ("p", "2004"), ("e", "Facebook")]
    assert tl[2]["parent"] == tl[1]["uid"]


def test_the_flat_blocks_are_accepted_by_the_backend_model():
    from tessellate.api.routes_drafts import KindModelIn

    for kind, source in (("mindmap", MM), ("timeline", TL), ("sequence", SEQ)):
        KindModelIn(nodes=_flat(kind, source))


def test_mind_map_add_under_a_named_branch_and_rename_and_delete():
    got = _play("mindmap", MM, "add Rent under Budget. rename Hiring to Recruiting. delete Salaries")
    assert got["r"]["done"] == 3 and got["r"]["lines"][0] == "Add Rent"
    printed = got["printed"]
    assert "Rent" in printed and "Recruiting" in printed and "Hiring" not in printed and "Salaries" not in printed
    assert printed.index("Rent") > printed.index("Budget") and printed.index("Rent") < printed.index("Recruiting")


def test_mind_map_move_goes_under_the_new_parent():
    got = _play("mindmap", MM, "move Salaries under Hiring")
    lines = got["printed"].splitlines()
    depth = {t.strip(): len(t) - len(t.lstrip()) for t in lines}
    assert depth["Salaries"] > depth["Hiring"] and lines.index(next(t for t in lines if "Salaries" in t)) > lines.index(next(t for t in lines if "Hiring" in t))


def test_timeline_event_under_a_period_and_a_new_section():
    got = _play("timeline", TL, "add event Launch under 2004. add section Later")
    assert got["r"]["done"] == 2
    assert "Launch" in got["printed"] and "section Later" in got["printed"]


def test_sequence_new_participant_then_a_message_to_it_in_one_ask():
    got = _play("sequence", SEQ, "add participant Courier. add message Ship from Shop to Courier")
    assert got["r"]["done"] == 2
    printed = got["printed"]
    assert "Courier" in printed and "Ship" in printed
    assert "->>" in printed.splitlines()[-1] and "Ship" in printed.splitlines()[-1]


def test_deleting_a_participant_takes_its_messages():
    got = _play("sequence", SEQ, "delete Bank")
    assert "hi" not in got["printed"] and "Bank" not in got["printed"]


def test_an_op_that_does_not_apply_is_dropped_not_forced():
    n = _node("mindmap", MM, "return dakApply(A, ko, m, [{op:'rename',target:'zzz',text:'x'},{op:'add',type:'b',text:'Q',parent:'zzz'},{op:'delete',target:'../x'}]);")
    assert n["done"] == 0 and n["lines"] == []


def test_source_the_ask_form_is_shown_for_every_kind_and_one_undo_step():
    ai = (JS / "diagram-ai.js").read_text(encoding="utf-8")
    assert 'if (S.k) form.classList.add("hidden")' not in ai
    assert 'ensureModule("diagramAiKinds")' in ai and "if (S.k) return askKind(A, words)" in ai
    assert ai.count("h.commit(S,") == 1  # preview and Apply are shared, so a kind's ask is one Undo step too
    assert 'diagramAiKinds: ["/js/diagram-ai-kinds.js"]' in (JS / "documents-mermaid.js").read_text(encoding="utf-8")
    kinds = (JS / "diagram-ai-kinds.js").read_text(encoding="utf-8")
    assert "textContent" not in kinds and "innerHTML" not in kinds
