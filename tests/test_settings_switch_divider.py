"""A hung Settings switch row's hairline stops where its group head's does.

INBOX 464 (2) hung each switch row's padding outside the group's column
(`margin-inline: calc(-1 * var(--space-3) - 1px)`) so the switch stands on
the text edge; the row's top border went with it, 9px past the head's
underline each side (464 (13), measured on 67 rows at 1440). The line is now
an inset background image whose width takes back exactly what the hang adds,
and the Tools grid's track can no longer be wider than a phone's column.
The browser half is `scratchpad/ui-sweeps/switchdepth2.js switchdivider`'s overhang,
0/0 on every row at 1440 and 390.
"""
import re
from pathlib import Path
from tests._css_paths import FORMER_08, sheets

CSS = Path(__file__).resolve().parents[1] / "frontend" / "css"
CONSISTENCY = sheets(*FORMER_08)
WIDGETS = (CSS / "03-dashboard-widgets.css").read_text(encoding="utf-8")


def test_the_inset_takes_back_what_the_hang_adds():
    hang = re.search(r"margin-inline:\s*calc\(-1 \* var\(--space-3\) - 1px\)", CONSISTENCY)
    assert hang, "the hang rule moved; re-measure the divider"
    m = re.search(
        r"#tool-list > li > \.setting-check\):is\(label\)[^{]*\{([^}]*)\}", CONSISTENCY
    )
    assert m, "the inset divider rule is missing"
    body = m.group(1)
    assert "border-top-color: transparent" in body
    assert "background-image: linear-gradient(var(--divider), var(--divider))" in body
    assert "background-size: calc(100% - 2 * var(--space-3) - 2px) 1px" in body


def test_the_tool_grid_fits_a_phone_column():
    m = re.search(r"#tool-list\s*\{([^}]*)\}", WIDGETS)
    assert "minmax(min(17rem, 100%), 1fr)" in m.group(1)
