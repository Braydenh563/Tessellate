"""Mermaid is vendored, lazy, and drawn in a frame with a policy of its own
(BACKLOG, "Diagrams: mermaid as the interchange format", steps 8, 12b and 13).

The reasons worth a test: the app's `style-src 'self'` refuses what Mermaid
writes, so the drawing lives in a separate same-origin document whose response
carries its own policy, while the app's policy is left exactly as it was; the
library must never reach the boot scripts; and the frame answers only the
window that framed it.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from tests._app_js import app_js_files

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "frontend" / "vendor" / "mermaid"
FRAME_JS = ROOT / "frontend" / "js" / "mermaid-frame.js"
DRAW_JS = ROOT / "frontend" / "js" / "mermaid-draw.js"


def test_the_library_is_vendored_with_its_licence_and_version_note() -> None:
    assert (VENDOR / "mermaid.min.js").stat().st_size > 1_000_000
    assert "MIT License" in (VENDOR / "LICENSE").read_text(encoding="utf-8")
    assert "12.2.0" in (VENDOR / "VERSION.txt").read_text(encoding="utf-8")
    row = [
        line
        for line in (ROOT / "docs" / "THIRD_PARTY.md").read_text(encoding="utf-8").splitlines()
        if line.startswith("| Mermaid |")
    ]
    assert row and "MIT" in row[0] and "12.2.0" in row[0]


def test_nothing_that_loads_at_boot_names_mermaid() -> None:
    """Lazy: not a boot script, not in index.html, never from a CDN."""
    index = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    loaded = re.findall(r'<(?:script|link)[^>]+(?:src|href)="([^"]+)"', index)
    assert not [url for url in loaded if "mermaid" in url.lower()], "mermaid is loaded at boot"
    boot = {path.name for path in app_js_files()}
    assert not {"mermaid-draw.js", "mermaid-frame.js"} & boot
    for path in app_js_files():
        text = path.read_text(encoding="utf-8")
        assert "mermaid.min.js" not in text, path.name
        assert not re.search(r"https?://[^\"'\s]*mermaid", text), path.name


def test_the_client_module_is_a_lazy_bundle_and_the_library_is_only_in_the_frame() -> None:
    app = (ROOT / "frontend" / "js" / "app.js").read_text(encoding="utf-8")
    block = app.split("const LAZY_MODULES = {", 1)[1].split("\n};", 1)[0]
    assert re.search(r'mermaid:\s*\[[^\]]*"/js/mermaid-draw\.js"', block)
    assert "/vendor/mermaid/" not in app, "only the frame's page may load the library"
    from tessellate.core import security

    assert "/vendor/mermaid/mermaid.min.js" in security.MERMAID_FRAME_HTML
    assert "/js/mermaid-frame.js" in security.MERMAID_FRAME_HTML


def test_the_frame_route_sends_its_own_policy_and_the_page_policy_is_unchanged(client) -> None:
    frame = client.get("/mermaid-frame")
    assert frame.status_code == 200
    policy = frame.headers["content-security-policy"]
    assert policy == (
        "default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src data:; "
        "font-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'self'"
    )
    assert frame.headers["x-frame-options"] == "SAMEORIGIN"
    assert "<script>" not in frame.text, "no inline script: the policy has no hash for one"

    page = client.get("/").headers["content-security-policy"]
    directives = dict(part.strip().split(" ", 1) for part in page.split(";") if part.strip())
    assert directives["style-src"] == "'self'"
    assert directives["img-src"] == "'self' data: blob:"
    assert directives["frame-ancestors"] == "'none'"
    assert "'unsafe-inline'" not in directives["script-src"]
    assert "'unsafe-eval'" not in page


def _run_region(path: Path, begin: str, end: str, body: str):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    text = path.read_text(encoding="utf-8")
    region = text[text.index(begin) : text.index(end)]
    assert "document." not in region and "window." not in region
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as handle:
        handle.write(region + "\n" + body)
    try:
        out = subprocess.run([node, handle.name], capture_output=True, text=True, timeout=30, check=True)
    finally:
        Path(handle.name).unlink(missing_ok=True)
    return json.loads(out.stdout)


FRAME_BEGIN, FRAME_END = "// MERMAID-FRAME-PROTOCOL-BEGIN", "// MERMAID-FRAME-PROTOCOL-END"


def test_the_frame_answers_only_its_parent_from_its_own_origin() -> None:
    body = """
const parent = {}; const other = {};
const good = { origin: "http://a", source: parent, data: { type: "render", id: "1", source: "pie" } };
const out = {
  good: mermaidFrameAccepts(good, parent, "http://a"),
  otherOrigin: mermaidFrameAccepts({ ...good, origin: "http://evil" }, parent, "http://a"),
  otherSource: mermaidFrameAccepts({ ...good, source: other }, parent, "http://a"),
  noType: mermaidFrameAccepts({ ...good, data: { id: "1", source: "pie" } }, parent, "http://a"),
  numberId: mermaidFrameAccepts({ ...good, data: { type: "render", id: 1, source: "pie" } }, parent, "http://a"),
  nothing: mermaidFrameAccepts(null, parent, "http://a"),
};
console.log(JSON.stringify(out));
"""
    out = _run_region(FRAME_JS, FRAME_BEGIN, FRAME_END, body)
    assert out == {
        "good": True, "otherOrigin": False, "otherSource": False, "noType": False, "numberId": False, "nothing": False,
    }


def test_an_error_is_one_short_line_and_variables_stay_plain() -> None:
    body = """
const long = "x".repeat(400);
console.log(JSON.stringify({
  multi: mermaidReasonLine(new Error("Parse error on line 2:\\n...A --> \\n-----^\\nExpecting 'SEMI'")),
  empty: mermaidReasonLine(""),
  clipped: mermaidReasonLine(long).length,
  vars: mermaidFrameVariables({ primaryColor: "#aabbcc", darkMode: true, "bad key": "#fff", evil: "url(javascript:alert(1));{", fontFamily: "system-ui, sans-serif" }),
}));
"""
    out = _run_region(FRAME_JS, FRAME_BEGIN, FRAME_END, body)
    assert out["multi"] == "Parse error on line 2. Expecting 'SEMI'"
    assert out["empty"] == "This is not a diagram Mermaid can read."
    assert out["clipped"] == 160
    assert out["vars"] == {"primaryColor": "#aabbcc", "darkMode": True, "fontFamily": "system-ui, sans-serif"}


DRAW_BEGIN, DRAW_END = "// MERMAID-DRAW-PROTOCOL-BEGIN", "// MERMAID-DRAW-PROTOCOL-END"


def test_the_page_takes_a_result_only_from_its_frame() -> None:
    body = """
const frame = {}; const other = {};
const ok = { origin: "http://a", source: frame, data: { type: "result", id: "m1", svg: "<svg/>" } };
console.log(JSON.stringify({
  good: mermaidResultAccepts(ok, frame, "http://a"),
  ready: mermaidResultAccepts({ ...ok, data: { type: "ready" } }, frame, "http://a"),
  otherOrigin: mermaidResultAccepts({ ...ok, origin: "http://evil" }, frame, "http://a"),
  otherSource: mermaidResultAccepts({ ...ok, source: other }, frame, "http://a"),
  noFrame: mermaidResultAccepts(ok, null, "http://a"),
  junk: mermaidResultAccepts({ ...ok, data: "result" }, frame, "http://a"),
}));
"""
    out = _run_region(DRAW_JS, DRAW_BEGIN, DRAW_END, body)
    assert out == {
        "good": True, "ready": True, "otherOrigin": False, "otherSource": False, "noFrame": False, "junk": False,
    }


def test_the_alt_text_comes_from_the_diagram() -> None:
    body = """
console.log(JSON.stringify([
  mermaidAltFor("pie title Pets\\n  \\"Dogs\\": 3"),
  mermaidAltFor("flowchart TD\\n  accTitle: Release steps\\n  A --> B"),
  mermaidAltFor("---\\ntitle: Sign in\\n---\\nsequenceDiagram\\nA->>B: hi"),
  mermaidAltFor("%% note\\nerDiagram\\n A ||--o{ B : has"),
  mermaidAltFor(""),
]));
"""
    out = _run_region(DRAW_JS, DRAW_BEGIN, DRAW_END, body)
    assert out == [
        "Pie chart: Pets",
        "Flowchart: Release steps",
        "Sequence diagram: Sign in",
        "Entity relationship diagram",
        "Diagram",
    ]
