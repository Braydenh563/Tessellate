"""The board's shape kind menu in a phone's Tools sheet (L-world-class-412, toolpop.js at 390).

It opened above its button, as on the floating bar; in the sheet that put it over the card's
top edge (menu top 267, card top 299), the card's overflow cut it off and a tap on Line fell
through to the overlay. A board rule, it lives in the board's lazy stylesheet (boot CSS cap). Measured after: the menu 575 to 821 inside a card 299 to 844.
"""

import re
from pathlib import Path

CSS = (Path(__file__).resolve().parents[1] / "frontend" / "css" / "library-lazy.css").read_text(encoding="utf-8")


def test_the_kind_menu_opens_below_its_button_in_a_sheet():
    rule = re.search(r"\n\.sheet-card \.wb-shape-menu \{([^}]*)\}", CSS)
    assert rule, "the sheet's kind menu rule moved"
    assert re.search(r"bottom:\s*auto;", rule.group(1)) and re.search(r"top:\s*calc\(100% \+ 0\.5rem\);", rule.group(1))
