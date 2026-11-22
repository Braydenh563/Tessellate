"""Source text: the menu sweep's page error "setDocView is not defined" at documents.js:235 (2026-11-22, every width).
The idle warm-up puts the Library bundle on the page one file at a time (lazy-entries.js), and documents-view.js,
early in that bundle, fetched documents.js on its own, so it ran before documents-surface.js had put `setDocView`
on window. A file inside a bundle waits for its bundle, never for a later file of it alone.
"""

from __future__ import annotations

import re
from pathlib import Path

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"


def _library_files() -> list[str]:
    app = (JS / "app.js").read_text(encoding="utf-8")
    block = app[app.index("  library: [") :]
    block = block[: block.index("\n  ],")]
    return re.findall(r'"/js/([\w.-]+\.js)"', block)


def test_no_library_file_fetches_a_later_file_of_its_own_bundle_alone() -> None:
    files = _library_files()
    assert "documents-view.js" in files and "documents.js" in files
    for i, name in enumerate(files):
        source = (JS / name).read_text(encoding="utf-8")
        for later in files[i + 1 :]:
            assert f'lazyScript("/js/{later}")' not in source, f"{name} fetches {later}, a later file of its own bundle"


def test_the_code_tools_wait_for_the_whole_library_bundle() -> None:
    view = (JS / "documents-view.js").read_text(encoding="utf-8")
    assert 'ensureModule("library").then(() => lazyScript("/js/documents-ide.js"))' in view
