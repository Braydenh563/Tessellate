"""A toast fired from a phone sheet is drawn over it (GRAPH_PLAN, built after
KG1 to KG9).

`openSheet` puts a sheet one layer above whatever it was opened from, so a
sheet opened from a menu (2550) or the table view (2400) is drawn at 2551 or
above, and `#toast-box` at 1050 was behind it: the confirmation of the thing
done in the sheet was never seen. Measured at 390x844 with
`scratchpad/ui-sweeps/toastsheet.js` (`elementFromPoint` at the toast's
centre): covered when the opener sat at 1050 or higher.

The browser half is that script; this is the lint that keeps the number above
the highest layer a sheet can be opened from and below the boot splash.
"""

from __future__ import annotations

import re
from pathlib import Path

CSS = Path(__file__).resolve().parents[1] / "frontend" / "css"

#: The highest fixed layer a sheet is opened from (the pointer-anchored menu
#: host, `.pointer-menu-host` in 02-chat-graph.css) and the first layer a toast must
#: not reach (the boot splash).
HIGHEST_OPENER = 2600
BOOT_SPLASH = 3000


def _phone_toast_z() -> int:
    text = (CSS / "10-responsive.css").read_text(encoding="utf-8")
    zs: list[int] = []
    for block in re.finditer(r"@media \(max-width: 599\.98px\) \{(.*?)\n\}\n", text, re.S):
        for body in re.findall(r"#toast-box\s*\{([^}]*)\}", block.group(1)):
            zs += [int(m) for m in re.findall(r"z-index:\s*(\d+)", body)]
    assert zs, "no phone rule gives #toast-box a z-index"
    return max(zs)


def test_the_phone_toast_box_is_above_every_layer_a_sheet_opens_from():
    z = _phone_toast_z()
    assert HIGHEST_OPENER < z < BOOT_SPLASH, z


def test_the_named_layers_are_still_where_this_test_says():
    menu = (CSS / "02-chat-graph.css").read_text(encoding="utf-8")
    assert "z-index: 2600;" in menu
    base = (CSS / "00-tokens-shell.css").read_text(encoding="utf-8")
    assert "z-index: 3000;" in base
