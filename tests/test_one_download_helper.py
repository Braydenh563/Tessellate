"""One way to hand the person a file (audit 2026-10-05, FE-16).

The hidden-anchor download (`URL.createObjectURL`, `a.download = ...`,
`a.click()`) was written out in four files, and each copy did nothing in the
desktop window, which swallows the click (skills.js's "saving a generated
file" note). `saveFile` covers both shells and `downloadBlob` is its browser
half; nothing else sets a download name.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests._app_js import documents_text

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"

#: The lightbox's Save follows a URL it already has, and leaves `download`
#: unset for a document on purpose so the server's own file name wins.
ALLOWED = {"lightbox-view.js"}


def test_only_the_helper_names_a_download():
    found = []
    for path in sorted(JS.glob("*.js")):
        if path.name in ALLOWED:
            continue
        for _ in re.finditer(r"\.download\s*=", path.read_text(encoding="utf-8")):
            found.append(path.name)
    assert found == ["skills.js"], found


def test_the_helper_is_the_browser_half_of_save_file():
    text = (JS / "skills.js").read_text(encoding="utf-8")
    save = text[text.index("async function saveFile(") :]
    save = save[: save.index("\n}\n")]
    assert "downloadBlob(blob, filename)" in save
    assert "function downloadBlob(blob, filename)" in text


def test_the_markdown_export_is_the_shared_export():
    text = documents_text()
    body = text[text.index("function exportDocumentMarkdown()") :][:200]
    assert 'downloadDocumentExport("export.md", "document.md")' in body
