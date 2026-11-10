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


def test_every_dock_menu_checkbox_row_carries_the_switch_class():
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    rows = re.findall(r'<label class="([^"]*\bdock-menu-check\b[^"]*)"[^>]*>\s*<input type="checkbox"', html)
    assert len(rows) >= 4
    assert all("checkbox-label" in r.split() or "semantic-toggle" in r.split() for r in rows), rows
    assert '.checkbox-label>input[type="checkbox"]:not(.sr-only),' in CSS


def test_a_dialog_label_stands_clear_of_its_field():
    """The owner, 2026-11-10, New space: "the border clashes with the name
    title". With no bottom margin the focus ring (2px at a 2px offset) drew
    through the label; measured gap 0, then 6px."""
    css = (ROOT / "frontend" / "css" / "07-whiteboard-misc.css").read_text(encoding="utf-8")
    body = css.split(".space-dialog label {", 1)[1].split("}", 1)[0]
    assert "margin-bottom: var(--space-2)" in body
