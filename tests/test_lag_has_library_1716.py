"""A node added anywhere in `<body>` no longer restyles the Library's picture tiles (INBOX 1716).

A browser cannot run in pytest, so these are static. The pin: on the Library Images tab (240 tiles, about
14,000 elements, 4x CPU, 2560x1504 at device scale 2) a trace of one `document.body.appendChild(span)` showed two
`ScheduleStyleInvalidationTracking changedPseudo: has` records on BODY and 976 "Related style rule" recalcs, one
per tile figure and one per tile tick (480 elements, two `UpdateLayoutTree` passes of 38 and 29ms). The cause was
the two `body:has(#library-media-selectbar:not(.hidden))` rules that show every tick while a selection is open.
The state now rides a body class set where the bar toggles (`syncLibraryMediaSelectbar`).
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = ROOT / "frontend" / "css"


def _css(name: str) -> str:
    return re.sub(r"/\*.*?\*/", "", (CSS / name).read_text(encoding="utf-8"), flags=re.S)


def test_no_tile_rule_keys_on_the_select_bar_through_has() -> None:
    for path in sorted(CSS.glob("*.css")):
        text = _css(path.name)
        assert "library-media-selectbar" not in text, f"{path.name} still reads the bar's state through :has()"


def test_the_ticks_stay_shown_while_a_selection_is_open_by_a_body_class() -> None:
    for name in ("07-whiteboard-misc.css", "07-whiteboard-misc.css"):
        text = _css(name)
        assert re.search(r"body\.library-media-selecting\s+\.library-image-tile[^{]*>\s*\.library-tile-tick", text), name


def test_the_class_is_set_where_the_bar_toggles() -> None:
    js = (ROOT / "frontend" / "js" / "library.js").read_text(encoding="utf-8")
    start = js.index("function syncLibraryMediaSelectbar(")
    fn = js[start : js.index("\n}\n", start)]
    assert 'bar.classList.toggle("hidden", n === 0)' in fn
    assert 'document.body.classList.toggle("library-media-selecting", n > 0)' in fn
    # One change point: nothing else flips the bar, so nothing else has to flip the class.
    assert len(re.findall(r'getElementById\("library-media-selectbar"\)|\$\("library-media-selectbar"\)', js)) == 1, "a new writer of the bar needs the class too"


def test_the_body_has_ratchet_lost_both_entries() -> None:
    ratchet = (ROOT / "tests" / "test_css_body_has.py").read_text(encoding="utf-8")
    assert "ALLOWED = set()" in ratchet
