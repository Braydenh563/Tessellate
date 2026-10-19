"""A toast over the Graph is opaque and stands clear of the map's controls
(INBOX 1306, the owner: "notifications are hard to see on the graph").

Measured with `scratchpad/ui-sweeps/graphtoast1306.js` on the Glass look,
dark, 1440x900: the toast's background was `--card` at alpha 0.549, so the
colour legend and the zoom strip read through it, and the box (1140..1424 by
774..855) overlapped the zoom strip (1369..1411 by 684..834). The browser
half is that sweep; this holds the two CSS shapes.
"""

from __future__ import annotations

import re
from pathlib import Path

CSS = Path(__file__).resolve().parents[1] / "frontend" / "css"


def _block(text: str, selector: str) -> str:
    m = re.search(r"(?m)^" + re.escape(selector) + r"\s*\{([^}]*)\}", text)
    assert m, f"no `{selector}` rule"
    return m.group(1)


def test_a_toast_is_painted_on_the_opaque_surface_not_the_glass_card() -> None:
    body = _block((CSS / "01-forms-settings.css").read_text(encoding="utf-8"), ".toast")
    assert re.search(r"background:\s*var\(--modal-bg-opaque\)", body)
    assert "--card" not in body and "backdrop-filter" not in body


def test_the_graph_lifts_the_toast_box_above_the_zoom_strip() -> None:
    text = (CSS / "03-dashboard-widgets.css").read_text(encoding="utf-8")
    m = re.search(r":root body:has\(#tab-graph:not\(\.hidden\)\) #toast-box\s*\{([^}]*)\}", text)
    assert m, "the Graph tab gives #toast-box no offset of its own"
    assert "12rem" in m.group(1)
