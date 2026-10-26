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
    assert "preview.textContent = body;\n  }\n}" in _js("math-editor.js")

