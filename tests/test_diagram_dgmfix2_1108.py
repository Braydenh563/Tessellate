"""Second blind sweep of the diagram builder (1108): what each fix must keep.

The numbers are in agent-remaining/dgmfix2-1108.md; these read the source for what has to stay true.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
BAR = (JS / "diagram-bar.js").read_text(encoding="utf-8")
BUILDER = (JS / "diagram-builder.js").read_text(encoding="utf-8")
KINDS = (JS / "diagram-kinds.js").read_text(encoding="utf-8")


def test_the_builder_keeps_ctrl_z_for_itself_wherever_focus_is_inside_it():
    """The app's undo listener is on the document: a press on a tile or the picture also binned the new document."""
    assert "function historyKey(" in BAR
    assert "event.stopPropagation()" in BAR.split("function historyKey(")[1].split("\n  }\n")[0]
    assert "diagramModel.bar.historyKey(S, event)" in BUILDER
    assert "diagramModel.bar.historyKey(S, event)" in KINDS
