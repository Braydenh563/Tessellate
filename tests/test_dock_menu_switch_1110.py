"""A checkbox in a dock menu is the app's pill switch, not a 28px platform box.

The owner, 2026-11-10, on Timeline, Options, "Dates beside the strip": "this
radio button is massive". The global `input[type="checkbox"]` target floor
sized the bare input to 28x28; measured after the fix at 32x18, the same as
the Semantic switch beside it in the search dock.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "frontend" / "css" / "06-timeline-dialogs.css").read_text(encoding="utf-8")


def test_the_switch_recipe_covers_dock_menu_checkboxes():
    for state in ("", "::after", ":hover", ":checked", ":checked::after"):
        sel = '.dock-menu-check > input[type="checkbox"]' + state + ","
        assert sel in CSS, sel
    body = CSS.split('.dock-menu-check > input[type="checkbox"],', 1)[1].split("{", 1)[1]
    head = re.sub(r"/\*.*?\*/", "", body, flags=re.S).split("}", 1)[0]
    assert re.search(r"appearance:\s*none", head) and "min-height: 1.15rem" in head


def test_a_dialog_label_stands_clear_of_its_field():
    """The owner, 2026-11-10, New space: "the border clashes with the name
    title". With no bottom margin the focus ring (2px at a 2px offset) drew
    through the label; measured gap 0, then 6px."""
    css = (ROOT / "frontend" / "css" / "07-whiteboard-misc.css").read_text(encoding="utf-8")
    body = css.split(".space-dialog label {", 1)[1].split("}", 1)[0]
    assert "margin-bottom: var(--space-2)" in body
