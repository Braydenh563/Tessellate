"""Source-text and node-executed checks for the review-findings batch."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _js(name: str) -> str:
    return (ROOT / "frontend" / "js" / name).read_text(encoding="utf-8")


def test_agent_commit_files_deletes_imported_documents_on_failure():
    src = _js("palette.js")
    body = src[src.index("async function agentCommitFiles") :]
    body = body[: body.index("\n}\n")]
    assert "for (const id of sent.documentIds)" in body
    assert "`/documents/${id}`" in body


def test_math_names_do_not_find_prototype_members(tmp_path):
    import json
    import shutil
    import subprocess

    import pytest

    node = shutil.which("node")
    if not node:
        pytest.skip("node is not available")
    text = _js("documents.js")
    src = text[text.index("// DOC-MATH-BEGIN") : text.index("// DOC-MATH-END")]
    driver = r"""
const out = {};
for (const tex of ["\\begin{constructor} a \\end{constructor}", "\\toString", "x \\hasOwnProperty y", "\\__proto__{a}"]) {
  try { out[tex] = JSON.stringify(docMathTree(tex, true)).length > 0; } catch (e) { out[tex] = "threw: " + e.message; }
}
console.log(JSON.stringify(out));
"""
    script = tmp_path / "run.js"
    script.write_text(src + driver, encoding="utf-8")
    run = subprocess.run([node, str(script)], capture_output=True, text=True, timeout=60, check=False)
    assert run.returncode == 0, run.stderr
    assert all(v is True for v in json.loads(run.stdout).values()), run.stdout


def test_math_render_failures_show_the_source():
    assert "host.textContent = this.tex" in _js("documents.js")
    #: The guided editor's own preview, which this once also pinned, went with the
    #: in-place equation field (a9a01e5): MathLive draws the field itself and its
    #: LaTeX toggle shows the source, so the document's widget is the one fallback left.
    assert "LaTeX" in _js("math-field.js")


def test_untouched_drop_is_limited_to_documents_made_this_session():
    src = _js("documents.js")
    drop = src[src.index("async function docDropIfUntouched") :]
    drop = drop[: drop.index("\n}\n")]
    assert "docsMadeThisSession.has(doc.id)" in drop
    made = src[src.index("async function ensureDocumentExists") :]
    made = made[: made.index("\n}\n")]
    assert "docsMadeThisSession.add(doc.id)" in made


def test_web_row_always_toggles_and_button_title_says_what_a_click_does():
    assert "afterPress(() => toggleWebSearch())" in _js("editor.js")
    assert 'press("web-search-toggle")' not in _js("editor.js")
    wiring = _js("wiring.js")
    assert "toggleWebSearch({ openFirst: true })" in wiring
    assert "if (openFirst && prefsCache?.web_search_enabled" in wiring
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert "a click opens the panel" in html[html.index('id="web-search-toggle"') :][:400]


def test_turning_graph_autofit_on_clears_the_moved_camera_and_refits():
    canvas = _js("graph-canvas.js")
    fn = canvas[canvas.index("function gcAutoFitTurnedOn") :]
    fn = fn[: fn.index("\n}\n")]
    assert "s.userZoomed = false" in fn and "gcRefitForPanels(s)" in fn
    assert "gcAutoFitTurnedOn()" in _js("graph.js")
