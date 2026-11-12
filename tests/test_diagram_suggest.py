"""What the diagram block pane is offered (1546 P3; DOCUMENTS_PLAN "1546 design" D8).

Three ways in, one way out: templates (eight flowcharts in `diagram-templates.json`),
From my notes and Describe it (both `POST /drafts/compose` with `kind: "diagram"`),
and the ghosts that a suggestion becomes on a diagram that already has blocks. The
route answers what the builder needs (`diagram`, or `diagram_error`: one sentence of
why a reply holds no diagram); the merge that renumbers a ghost's ids runs in node
beside the model and the ops. The dialog, the keys and the pictures are measured in
the running app (scratchpad/ui-sweeps/diagram-blocks.js, mode `suggest`).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from tessellate.ai import composer_mermaid as cm
from tests._app_js import lazy_modules_source

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
BUILDER = JS / "diagram-builder.js"
OPS = JS / "diagram-ops.js"
SUGGEST = JS / "diagram-suggest.js"
MERMAID = JS / "documents-mermaid.js"
TEMPLATES = ROOT / "frontend" / "board-library" / "diagram-templates.json"

CHECKLIST = "- [ ] Draft the brief\n- [ ] Review with Sam\n- [ ] Fix comments\n- [ ] Send to client\n- [x] Archive the file"
HEADINGS = "# Garden plan\n## Soil\n## Seeds\n## Water\n## Harvest"


def _region(path: Path, name: str) -> str:
    text = path.read_text(encoding="utf-8")
    return text[text.index(f"// {name}-BEGIN") : text.index(f"// {name}-END")]


def _node(body: str):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    code = "\n".join(
        [_region(MERMAID, "DIAGRAM-MODEL"), _region(OPS, "DIAGRAM-OPS"), _region(SUGGEST, "DIAGRAM-GHOST"), body]
    )
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as handle:
        handle.write(code)
    try:
        out = subprocess.run([node, handle.name], capture_output=True, text=True, timeout=60, check=True)
    finally:
        Path(handle.name).unlink(missing_ok=True)
    return json.loads(out.stdout)


def _fence_body(draft: str) -> str:
    found = re.search(r"```mermaid\n(.*?)\n```", draft, re.S)
    assert found, draft
    return found.group(1)


def _compose(client, **body):
    reply = client.post("/drafts/compose", json={"kind": "diagram", **body})
    assert reply.status_code == 200, reply.text
    return reply.json()


# --- the templates -------------------------------------------------------------------


def test_twenty_flowcharts_each_read_back_as_blocks_the_printer_writes_unchanged():
    #: 1546 P4 added a mind map, a timeline and two sequence diagrams (each with a `kind`); they are
    #: held to the same rule by tests/test_diagram_kinds.py, so this one stays the flowcharts'.
    rows = [t for t in json.loads(TEMPLATES.read_text(encoding="utf-8"))["templates"] if "kind" not in t]
    #: 1679 slice 9 moved the intent from "eight" to fourteen: an org chart and an architecture lead, then
    #: the first seven, then a lifecycle, a checklist, sideways lanes and a loop, and Blank last. R16 (OPEN W18, 1109) added six
    #: more before Blank: an incident, a release, a ticket, a hire, an order and a content review.
    assert [t["id"] for t in rows] == [
        "org-chart", "architecture", "process", "decision", "approval", "onboarding", "bug-triage", "user-flow",
        "swimlanes", "state-lifecycle", "checklist-flow", "swimlanes-sideways", "request-loop",
        "incident-response", "release-pipeline", "support-ticket", "hiring-pipeline", "order-fulfilment", "content-review", "blank",
    ]  # fmt: skip
    got = _node(
        f"const rows = {json.dumps(rows)};\n"
        "console.log(JSON.stringify(rows.map((t) => { const m = diagramModel.parse(t.source);"
        " return { id: t.id, nodes: m.nodes.length, edges: m.edges.length, groups: m.subgraphs.length,"
        " kept: m.kept.length, same: diagramModel.print(m) === t.source,"
        " known: m.edges.every((e) => m.nodes.some((n) => n.id === e.from) && m.nodes.some((n) => n.id === e.to)) }; })));"
    )
    by_id = {row["id"]: row for row in got}
    assert all(row["same"] and row["kept"] == 0 and row["known"] for row in got), got
    assert by_id["blank"]["nodes"] == 0 and by_id["swimlanes"]["groups"] == 3
    assert by_id["architecture"]["groups"] == 3 and by_id["swimlanes-sideways"]["groups"] == 3
    assert by_id["org-chart"]["groups"] == 0 and by_id["org-chart"]["edges"] == by_id["org-chart"]["nodes"] - 1
    assert all(row["nodes"] >= 5 for row in got if row["id"] != "blank")
    # Every other one is a real diagram with a join for each box but one at least.
    assert all(row["nodes"] >= 5 and row["edges"] >= row["nodes"] - 1 for row in got if row["id"] not in ("blank",)), got
    # The decision, approval and triage flows ask a question: a diamond with two ways out.
    assert all(re.search(r"\{\"", next(t for t in rows if t["id"] == key)["source"]) for key in ("decision", "approval", "bug-triage"))


def test_template_copy_is_sentence_case_with_no_dash_or_exclamation():
    for t in json.loads(TEMPLATES.read_text(encoding="utf-8"))["templates"]:
        for words in (t["name"], t["hint"], *re.findall(r'"([^"]+)"', t["source"])):
            assert chr(0x2014) not in words and "!" not in words, words
        assert t["name"][0].isupper() and t["hint"].endswith(".")


def test_the_template_file_is_not_read_as_a_board_library_set():
    """`_builtin_index` globs every json in the folder for `items`; this file has none, so it adds no board shapes."""
    body = json.loads(TEMPLATES.read_text(encoding="utf-8"))
    assert "items" not in body and body["format"] == "tessellate-diagram-templates"


# --- the composer, by rule (no model) ---------------------------------------------------


def test_a_checklist_note_through_compose_is_a_flowchart_of_five_boxes_and_four_arrows(ai_client, fake_ollama):
    fake_ollama.running = False
    note = ai_client.post("/entries", json={"content": CHECKLIST}).json()
    body = _compose(ai_client, source_ids=[note["id"]])
    assert body["by"] == "composer" and not body["diagram_error"]
    source = body["diagram"]
    assert source == _fence_body(body["draft"]) + "\n"
    lines = [line.strip() for line in source.splitlines()]
    assert lines[0] == "flowchart TD"
    assert len([line for line in lines if re.match(r'^n\d+\["', line)]) == 5
    assert len([line for line in lines if re.match(r"^n\d+ --> n\d+$", line)]) == 4
    assert "Archive the file" in source


def test_a_documents_headings_through_compose_are_a_mind_map(ai_client, fake_ollama):
    fake_ollama.running = False
    body = _compose(ai_client, draft=HEADINGS, instruction="mind map")
    source = body["diagram"]
    assert source.startswith("mindmap\n") and 'root(("Garden plan"))' in source
    assert [m for m in re.findall(r'n\d+\["([^"]+)"\]', source)] == ["Soil", "Seeds", "Water", "Harvest"]


def test_sub_headings_with_points_nest_their_points_under_them():
    text = "# Garden plan\n## Soil\n- test ph\n- add compost\n## Seeds\n- tomatoes\n## Water"
    made = cm.diagram(text, want="mindmap")
    rows = [(len(line) - len(line.lstrip())) // 2 - 1 for line in made.source.splitlines()[2:]]
    assert rows == [1, 2, 2, 1, 2, 1], made.source


@pytest.mark.parametrize(
    ("text", "count"),
    [
        ("- [ ] one\n- [ ] two\n- [ ] three", 3),
        ("- [x] done already\n- [ ] still to do", 2),
        ("* [ ] a\n  * [ ] a sub task\n* [ ] b\n* [ ] c", 3),
    ],
)
def test_a_checklist_is_steps(text, count):
    assert len(cm.steps(text)) == count
    assert cm.diagram(text, want="").shape == "flowchart"


def test_one_task_is_not_a_flow():
    assert cm.steps("- [ ] buy milk") == []


# --- a model's reply, through the fake transport -----------------------------------------


def test_a_broken_fence_comes_back_a_reason_not_blocks(ai_client, fake_ollama):
    for reply, word in (
        ("```mermaid\nflowchart TD\n  a[\"Plan\"] --> b[\"Do\"]\n", "cut off"),
        ("Here is a nice diagram of your plan: plan, then do.", "in words"),
        ("```mermaid\nflowchart TD\n```", "nothing in it"),
        ("```mermaid\nnot a diagram at all\nstill not\n```", "in words"),
    ):
        fake_ollama.librarian_reply = reply
        body = _compose(ai_client, thoughts="plan then do")
        assert body["diagram"] == "", reply
        assert word in body["diagram_error"], (reply, body["diagram_error"])
        assert "!" not in body["diagram_error"] and chr(0x2014) not in body["diagram_error"]


def test_a_good_fence_is_the_source_and_a_bare_diagram_is_taken_too(ai_client, fake_ollama):
    fake_ollama.librarian_reply = "```mermaid\nflowchart TD\n  a[\"Plan\"] --> b[\"Do\"]\n```"
    body = _compose(ai_client, thoughts="plan then do")
    assert body["diagram"] == 'flowchart TD\n  a["Plan"] --> b["Do"]\n' and not body["diagram_error"]
    fake_ollama.librarian_reply = "flowchart LR\n  a --> b"
    assert _compose(ai_client, thoughts="plan then do")["diagram"] == "flowchart LR\n  a --> b\n"


def test_a_model_that_is_down_gets_its_own_message_as_the_reason(ai_client, fake_ollama):
    fake_ollama.running = False
    body = _compose(ai_client, thoughts="", draft="Some words with no steps or dates or points.")
    assert body["diagram"] == "" and body["diagram_error"]


def test_other_kinds_of_pass_are_not_touched(ai_client, fake_ollama):
    fake_ollama.librarian_reply = "A shorter note."
    body = ai_client.post("/drafts/compose", json={"thoughts": "x", "draft": "y", "kind": "bullets"}).json()
    assert "diagram" not in body and body["draft"] == "A shorter note."


# --- the ghost merge (node) --------------------------------------------------------------


def test_the_ghost_merge_renumbers_ids_past_the_diagrams_own():
    got = _node(
        'const m = diagramModel.parse(\'flowchart TD\\n  A["One"]\\n  B["Two"]\\n  A --> B\\n\');'
        'const inc = diagramModel.parse(\'flowchart TD\\n  A(["Start"])\\n  B{"Ready?"}\\n  C["Go"]\\n  A --> B\\n  B -->|"Yes"| C\\n\');'
        "const done = dgsMerge(diagramOps, m, inc);"
        "console.log(JSON.stringify({ done: { ...done, map: [...done.map] }, ids: m.nodes.map((n) => n.id),"
        " edges: m.edges.map((e) => [e.from, e.to, e.label]), again: diagramModel.print(diagramModel.parse(diagramModel.print(m))) === diagramModel.print(m) }));"
    )
    assert got["ids"] == ["A", "B", "C", "D", "E"]
    assert got["done"]["map"] == [["A", "C"], ["B", "D"], ["C", "E"]]
    assert got["edges"] == [["A", "B", ""], ["C", "D", ""], ["D", "E", "Yes"]]
    assert got["again"] and got["done"]["nodes"] == 3 and got["done"]["edges"] == 2


def test_taken_blocks_only_and_a_join_needs_both_ends():
    got = _node(
        "const m = diagramModel.parse('flowchart TD\\n  A[\"One\"]\\n');"
        "const inc = diagramModel.parse('flowchart TD\\n  A[\"a\"]\\n  B[\"b\"]\\n  C[\"c\"]\\n  A --> B\\n  B --> C\\n');"
        "const done = dgsMerge(diagramOps, m, inc, new Set(['n:A', 'n:B']));"
        "console.log(JSON.stringify({ ids: m.nodes.map((n) => [n.id, n.text]), edges: m.edges.map((e) => [e.from, e.to]), skipped: done.skipped }));"
    )
    assert got["ids"] == [["A", "One"], ["B", "a"], ["C", "b"]]
    assert got["edges"] == [["B", "C"]]


def test_a_group_goes_in_before_what_it_holds_and_a_taken_group_takes_its_blocks():
    got = _node(
        "const m = diagramModel.parse('flowchart TD\\n  subgraph G1 [\"Mine\"]\\n    A[\"x\"]\\n  end\\n');"
        "const inc = diagramModel.parse('flowchart TD\\n  subgraph G1 [\"Lane\"]\\n    A[\"a\"]\\n    B[\"b\"]\\n  end\\n  C[\"c\"]\\n  A --> B\\n  B --> C\\n');"
        "const keys = dgsSubtree(inc, 'g:G1');"
        "const done = dgsMerge(diagramOps, m, inc, new Set(keys));"
        "console.log(JSON.stringify({ keys, groups: m.subgraphs.map((g) => [g.id, g.title, g.parent]), nodes: m.nodes.map((n) => [n.id, n.group]), edges: m.edges.map((e) => [e.from, e.to]), done: done.groups }));"
    )
    assert got["keys"] == ["g:G1", "n:A", "n:B"]
    assert got["groups"] == [["G1", "Mine", None], ["G2", "Lane", None]]
    assert got["nodes"] == [["A", "G1"], ["B", "G2"], ["C", "G2"]]
    assert got["edges"] == [["B", "C"]]


def test_the_merge_stops_at_the_panes_limit_and_says_how_many_did_not_fit():
    got = _node(
        "const m = diagramModel.parse('flowchart TD\\n');"
        "for (let i = 0; i < diagramOps.MAX - 1; i++) diagramOps.addNode(m);"
        "const inc = diagramModel.parse('flowchart TD\\n  A[\"a\"]\\n  B[\"b\"]\\n  C[\"c\"]\\n  A --> B\\n  B --> C\\n');"
        "const done = dgsMerge(diagramOps, m, inc);"
        "console.log(JSON.stringify({ nodes: m.nodes.length, added: done.nodes, skipped: done.skipped, edges: done.edges }));"
    )
    assert got == {"nodes": 120, "added": 1, "skipped": 2, "edges": 0}


# --- the module, read for what it must and must not contain -------------------------------


def test_suggest_builds_text_nodes_only_and_exports_one_name():
    code = SUGGEST.read_text(encoding="utf-8")
    body = re.sub(r"//.*", "", code)
    for banned in ("innerHTML", "insertAdjacentHTML", "outerHTML", "document.write", "DOMParser", '.setAttribute("style"', "onclick", ".style."):
        assert banned not in body, banned
    assert body.count("diagramModel.suggest =") == 1
    assert re.findall(r"^(?:async\s+)?function\s", body, re.M) == [], "a top-level name joins the shared scope"
    assert re.findall(r"^(?:const|let|var)\s", body, re.M) == []
    assert "textContent" in code or 'h.el("' in code


def test_the_ghosts_keep_the_ghost_topics_four_keys():
    code = SUGGEST.read_text(encoding="utf-8")
    assert 'aria-pressed' in code and "is-taken" in code
    for fragment in ('event.key === "Escape"', 'event.key === "Tab"', 'event.key === "Enter"', "event.shiftKey"):
        assert fragment in code, fragment
    assert 'role", "group"' in code and "Tab takes" in code


def test_the_template_dialog_is_the_dialog_of_choices_recipe_with_one_filled_button():
    code = SUGGEST.read_text(encoding="utf-8")
    for fragment in ("doc-template-choice", 'role", "radiogroup"', '"radio"', "aria-checked", "doc-template-body", "doc-template-preview", "space-dialog-actions", "dialogHead("):
        assert fragment in code, fragment
    #: Intent unchanged, the file gained the sheet of diagrams (R12), a second dialog of choices with its one filled button.
    assert code.count('go.classList.add("accent")') == 2 and "ghost" in code
    # Choosing is not making: a double click or Enter uses the row, a click only chooses.
    assert 'addEventListener("dblclick", use)' in code and 'addEventListener("click", () => choose(t))' in code


def test_describe_it_is_dimmed_with_its_reason_when_there_is_no_model():
    #: The rows moved out of the builder in 1546 P4 (the builder is back under its size target); the rule is the same.
    code = SUGGEST.read_text(encoding="utf-8")
    assert "disabled: off" in code and "needs a model" in code and "aiIsOff()" in code
    assert code.count('"describe"') == 1


def test_the_suggestions_are_a_bundle_of_their_own_never_at_boot():
    rows = lazy_modules_source()
    assert 'diagramSuggest: ["/js/diagram-suggest.js"]' in rows
    for boot in ("app.js", "lazy-entries.js"):
        assert "diagramSuggest" not in (JS / boot).read_text(encoding="utf-8"), boot
    assert "diagram-suggest.js" not in (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")


def test_the_template_picker_filters_and_the_door_offers_the_existing_diagrams():
    """1679 slice 9: fourteen rows are typed to through the one recipe, and the door's dialog opens a diagram that exists."""
    suggest = (ROOT / "frontend" / "js" / "diagram-suggest.js").read_text(encoding="utf-8")
    assert 'listFilter(list, { label: "Search the templates"' in suggest
    embed = (ROOT / "frontend" / "js" / "diagram-embed.js").read_text(encoding="utf-8")
    assert "existing" in embed and "Open an existing diagram" in embed
    #: Intent unchanged, the list moved (R12): the open-an-existing button asks the sheet, which lists the mmd documents (diagram-suggest.js).
    mermaid = (ROOT / "frontend" / "js" / "documents-mermaid.js").read_text(encoding="utf-8")
    assert 'file_type === "mmd"' in suggest and "chooseDiagram({ fresh: false })" in mermaid
