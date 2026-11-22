"""L-world-class-107 (INBOX 403, "that small gap between the edge of the note
connection pill chips on the right and the 'x'"): with a mouse the connection
pill's menu button ends flush and draws its circle 2px inside its 24px target,
so the circle sits 3px from the pill's outer edge on the top, the bottom and
the end. Measured before: 1, 1 and 3 (`scratchpad/ui-sweeps/pill-inset-107.js`)."""

from __future__ import annotations

import re
from pathlib import Path

CSS = (Path(__file__).resolve().parents[1] / "frontend" / "css" / "08-consistency.css").read_text(encoding="utf-8")


def test_the_pill_menu_button_is_concentric_with_a_mouse():
    fine = CSS[CSS.index("@media (pointer: fine) {\n  #entry-list .link-connection > .menu-wrap {") :]
    rule = re.search(r"#entry-list \.link-connection > \.menu-wrap > button \{([^}]*)\}", fine).group(1)
    assert "width: 1.5rem" in rule and "height: 1.5rem" in rule
    assert "margin-inline-end: 0" in rule
    assert "padding: 2px" in rule and "background-clip: content-box" in rule
