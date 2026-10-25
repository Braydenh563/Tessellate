"""INBOX 904 B21 and B22: a code file's forced Source must not outlive the file.

The owner: "I switched from a md document to a code document and then back to
md but it still thought it was and treated it like a code document", and "live
view on the document editor for md files should be default not source".

One cause: `setDocView` wrote every view it was given to the stored
`doc-view-mode`, including the Source it forces on a `.py` file, so the next
markdown document opened in Source and a type switch back to `.md` stayed there.
The browser check is `scratchpad/ui-sweeps/doctypeback.js`.
"""

from __future__ import annotations

import re
from pathlib import Path

DOCS_JS = Path(__file__).resolve().parents[1] / "frontend" / "js" / "documents.js"


def _function(name: str) -> str:
    text = DOCS_JS.read_text(encoding="utf-8")
    start = text.index(f"function {name}(")
    end = text.index("\n}\n", start)
    return text[start:end]


def test_set_doc_view_does_not_store_a_code_files_source():
    body = _function("setDocView")
    assert re.search(r"if\s*\(\s*!docViewState\.held\s*\)\s*prefs\.set\(DOC_VIEW_KEY", body), (
        "the store must be skipped while Source is only the code file's"
    )


def test_last_edit_view_ignores_a_held_source():
    body = _function("setDocView")
    assert re.search(r"lastEditView = docView", body)
    assert re.search(r"!docViewState\.held\)\s*lastEditView = docView", body)


def test_changing_back_to_a_markdown_type_restores_the_chosen_view():
    body = _function("syncDocFileType")
    assert re.search(r"type\.previewable && docViewState\.held\)\s*setDocView\(docDefaultView\(\)\)", body)


def test_default_view_is_live_and_shared_by_boot():
    body = _function("docDefaultView")
    assert '"live"' in body and "DOC_VIEW_KEY" in body
    text = DOCS_JS.read_text(encoding="utf-8")
    assert "setDocView(docDefaultView())" in text


def test_stored_view_from_before_the_version_key_resets_to_live_once():
    """A stored "source" from before the version key is dropped once; later choices stay."""
    import json
    import shutil
    import subprocess

    import pytest

    node = shutil.which("node")
    if not node:
        pytest.skip("node not installed")
    text = DOCS_JS.read_text(encoding="utf-8")
    migrate = _function("docViewMigrate")
    default = _function("docDefaultView")
    script = f"""
const store = {{ "doc-view-mode": "source" }};
globalThis.window = {{
  localStorage: {{
    getItem: (k) => (k in store ? store[k] : null),
    setItem: (k, v) => (store[k] = String(v)),
    removeItem: (k) => delete store[k],
  }},
  matchMedia: () => ({{ matches: false }}),
}};
const prefs = {{
  get: (k, f) => (k in store ? store[k] : f),
  has: (k) => k in store,
  set: (k, v) => (store[k] = String(v)),
  remove: (k) => delete store[k],
}};
const DOC_VIEW_KEY = "doc-view-mode";
const DOC_VIEW_VERSION_KEY = "doc-view-mode-v";
const DOC_VIEW_VERSION = "2";
{migrate}
}}
{default}
}}
const first = docDefaultView();
store["doc-view-mode"] = "split";
const second = docDefaultView();
console.log(JSON.stringify([first, second]));
"""
    assert "DOC_VIEW_VERSION" in text
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, check=True).stdout
    assert json.loads(out) == ["live", "split"]
