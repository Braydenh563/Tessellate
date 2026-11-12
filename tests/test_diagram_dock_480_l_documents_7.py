"""L-documents-7: at 480 px or less the diagram builder's dock is one row.

Direction, Ask for a change and Redo fold into the dock's ... menu (Undo, the blocks list, Add and the
menu stay), so five or six targets of 44 px or more share one row. The fold is a CSS rule for the
buttons and rows in `more()` for the same three.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
CSS = (ROOT / "frontend" / "css" / "diagram-lazy.css").read_text(encoding="utf-8")
BUILDER = (JS / "diagram-kindbar.js").read_text(encoding="utf-8")  # the narrow fold moved here from the builder (gzip budget)


def test_the_three_buttons_hide_at_480():
    rule = re.search(r"\.dgm-narrow \.dgm-dock :is\(([^)]*)\) \{([^}]*)\}", CSS)
    assert rule, "no dgm-narrow rule"
    assert all(name in rule.group(1) for name in (".dgm-dirs", ".dgm-askbtn", ".dgm-redo"))
    assert "display: none" in rule.group(2)
    assert 'S.root.classList.toggle("dgm-narrow", narrow)' in BUILDER


def test_redo_carries_the_class_in_both_docks():
    assert "dgm-redo" in (JS / "diagram-bar.js").read_text(encoding="utf-8")
    assert "dgm-redo" in (JS / "diagram-kinds.js").read_text(encoding="utf-8")


def test_the_menu_takes_the_three_rows_when_narrow():
    more = BUILDER[BUILDER.index("function fold(S") : BUILDER.index("diagramModel.kindbar =")]
    assert "max-width: 480px" in BUILDER
    for label in ("Direction", "Redo", "Ask for a change"):
        assert label in more
