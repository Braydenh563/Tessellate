"""L685 B: the companion's registered properties and the Atlas one-off plays
live in the lazy characters sheet, at its top, and not in the boot sheet.

Moving a rule to a sheet that loads later changes which equal-specificity
rule wins, so the move is only sound while nothing that loads between the old
place (08) and the new one (the top of characters-lazy.css) styles the same
parts. Measured identical in Chromium over 2,352 state combinations."""

from __future__ import annotations

import re
from pathlib import Path

CSS = Path(__file__).resolve().parent.parent / "frontend" / "css"
MOVED = ("--nmb-tilt", "--nmb-lean", "--nmb-ex", "--nmb-ey", "--nmb-hx", "--atl-lean-dir", "--nmb-lean-pose",
         "--nmb-lie-shift", "--atl-v1", "--atl-v2", "--atl-chin", "--atl-lean", "--atl-sx", "--atl-sy", "--atl-tail")
PARTS = re.compile(r"\.atl-(?:mood|head|sway)\b|\.nmb-arm-r\b|atl-play-")
#: A rule with an id (`#nm-buddy.nmb-act-*`) outranks the plays whichever sheet is
#: later, so only an id-less line can tie with them.
#: Sheets that load between 08 and characters-lazy in the page's order: the
#: rest of the boot sheets, and the lazy sheets a page can have in before it.
BETWEEN = ("09-editor.css", "10-responsive.css", "atlas-lazy.css", "companion-travel-lazy.css", "companion-throw-lazy.css", "desk-companion-lazy.css")


def test_the_moved_block_is_at_the_top_of_the_lazy_sheet_only():
    boot = (CSS / "08-consistency.css").read_text()
    lazy = (CSS / "characters-lazy.css").read_text()
    for name in MOVED:
        assert f"@property {name} " not in boot, name
        assert lazy.count(f"@property {name} ") == 1, name
    assert "atl-play-nod .atl-head" not in boot
    assert lazy.index("atl-play-nod .atl-head") < lazy.index(".atlas-mark:has(> .nm-atlas)")
    assert lazy.index("@property --nmb-tilt") < lazy.index(".atlas-mark:has(> .nm-atlas)")


def test_nothing_between_the_old_and_new_place_styles_the_same_parts():
    for name in BETWEEN:
        text = (CSS / name).read_text()
        hits = [line for line in text.splitlines() if PARTS.search(line) and "animation" in line and "#" not in line]
        assert not hits, f"{name} sets an animation on a part the moved plays style: {hits[:2]}"
