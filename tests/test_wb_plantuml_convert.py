"""PlantUML out and the Import dialog's routing (L-whiteboard-41, 45), run in node: the writer, the sniffing and
the positioned layout are pure, and the placing is checked as source (the browser half is the sweep)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tests._app_js import frontend_text

ROOT = Path(__file__).resolve().parents[1]
INTER = frontend_text("whiteboard-interchange.js")


def _run(body: str):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    graph = INTER[INTER.index("wbBoardToMermaid.graph = function") : INTER.index("//: Rows by depth from the nodes nothing points at")]
    placed = INTER[INTER.index("wbMermaidLayout.positioned = function") : INTER.index("//: A cap this board draws")]
    script = "const wbFmtState = {}; function wbBoardToMermaid() {} function wbMermaidLayout() {}\n" + graph + placed + frontend_text("whiteboard-plantuml.js") + frontend_text("whiteboard-convert.js") + "\n" + body
    return json.loads(subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=30, check=True).stdout)


STATE = """
const state = { nodes: [], objects: [{ id: 9, kind: "text", data: { content: "Outside \\"x\\"" } }],
  sketches: [
    { id: 1, data: JSON.stringify({ shape: "diamond", label: "Ready?" }) },
    { id: 2, data: JSON.stringify({ shape: "rect", label: "Ship" }) },
    { id: 3, data: JSON.stringify({ type: "link-straight", sourceId: 1, sourceKind: "sketch", targetId: 2, targetKind: "sketch", endCap: "arrow", label: "yes" }) },
    { id: 4, data: JSON.stringify({ type: "link-straight", sourceId: 2, sourceKind: "sketch", targetId: 9, targetKind: "object", dash: "dashed" }) },
  ] };
"""


def test_the_board_is_written_as_plantuml():
    text = _run(STATE + "console.log(JSON.stringify(wbFmtState.plantuml.text(wbBoardToMermaid.graph(state))));")
    lines = text.splitlines()
    assert lines[0] == "@startuml" and lines[-1] == "@enduml"
    assert 'diamond "Ready?" as n1' in lines and 'rectangle "Ship" as n2' in lines
    assert 'rectangle "Outside x" as n3' in lines, "a quote in the words would end the name, so it goes"
    assert "n1 --> n2 : yes" in lines and "n2 .. n3" in lines


def test_a_frame_is_a_package_round_what_it_holds():
    text = _run(STATE + 'console.log(JSON.stringify(wbFmtState.plantuml.text(wbBoardToMermaid.graph(state, undefined, (kind, item) => (kind === "sketch" && item.id === 2 ? { id: 7, title: "Release" } : null)))));')
    assert 'package "Release" {\n  rectangle "Ship" as n2\n}' in text


def test_the_import_dialog_sniffs_each_format():
    got = _run(
        'const s = wbFmtState.convert.sniff; console.log(JSON.stringify([s("<?xml version=\\"1.0\\"?><graphml xmlns=\\"x\\"></graphml>"), s("@startuml\\nA -> B\\n@enduml"),'
        ' s(\'{"data":[{"id":"1","type":"sticky_note"}]}\'), s("flowchart TD\\nA-->B"), s(\'{"hello": 1}\'), s("")]));'
    )
    assert got == ["graphml", "plantuml", "miro", None, None, None]


def test_a_file_that_kept_its_places_is_centred_and_its_frames_come_with_it():
    got = _run(
        'const g = { centred: true, nodes: [{ id: "a", x: 100, y: 100, w: 100, h: 50 }, { id: "b", x: 300, y: 100, w: 100, h: 50 }], frames: [{ id: "f", title: "F", x: 0, y: 0, w: 400, h: 200 }] };'
        "const p = wbMermaidLayout.positioned(g); console.log(JSON.stringify({ a: p.get('a'), b: p.get('b'), f: p.frames[0] }));"
    )
    # The frame box 0..400 by 0..200 is centred on 0, and so are the shapes with it.
    assert got["a"] == {"x": -100, "y": 0}
    assert got["b"] == {"x": 100, "y": 0} and got["f"]["x"] == -200 and got["f"]["y"] == -100


def test_the_dialog_routes_converted_files_and_emf_is_never_read_as_text():
    inter = INTER
    assert "wbFmtState.convert?.sniff(text)" in inter and "wbFmtState.convert.run({ format: other, content: text })" in inter
    assert "wbFmtState.convert.importEmf(chosen)" in inter and inter.index("importEmf(chosen)") < inter.index("const text = await chosen.text();")
    convert = frontend_text("whiteboard-convert.js")
    assert '"/whiteboard/convert"' in convert and "wbImportMermaid(null, at, got.graph)" in convert and "wbImportMermaidSequence(null, at, got.sequence)" in convert
    assert ".emf" in (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
