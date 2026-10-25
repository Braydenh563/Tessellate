"""Dogfood round 1 (2026-10-25) whiteboard and mind map fixes, fixer B.

Source-level checks the suite can see; the browser numbers are in the
commit messages and `docs/roadmap/agent-remaining/fixb-1025.md`.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WB = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")


def test_new_map_toast_says_what_enter_does_while_typing():
    # Enter in a topic's editor is a line break (the owner, 2026-10-10), so the
    # creation toast must name the key that adds a sibling while typing.
    assert "While typing a name, Ctrl+Enter adds the sibling." in WB
