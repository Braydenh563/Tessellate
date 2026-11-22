"""setDocView is called from other files (print, commands, diagrams), so documents-surface.js must put it on window.

Why: timeline found a base where it was not, and every document file threw at load (hub, 2026-11-22).
"""

import re

from pathlib import Path

JS = Path(__file__).resolve().parent.parent / "frontend" / "js" / "documents-surface.js"


def test_set_doc_view_is_on_window():
    js = JS.read_text(encoding="utf-8")  # raw: frontend_text unwraps the export
    exported = re.search(r"Object\.assign\(window, \{([^}]*)\}\)", js)
    assert exported, "documents-surface.js no longer exports through Object.assign(window, {...})"
    assert "setDocView" in [n.strip() for n in exported.group(1).split(",")]
