"""The reader's phone page must win over the card's desktop size.

`.ocr-card` (width 96vw, height 92vh) moved into library-lazy.css, which loads
after 10-responsive.css, so at equal specificity it beat `.sheet-card-page` and
the phone reader was 374 wide and 776 tall instead of the whole screen
(scratchpad/ui-sweeps/libreader.js at 390x844).
"""
import re
from pathlib import Path

CSS = Path(__file__).resolve().parent.parent / "frontend" / "css"


def test_ocr_card_size_yields_to_the_page_variant():
    lazy = (CSS / "library-lazy.css").read_text()
    rule = re.search(r"(?m)^(\.ocr-card[^{]*)\{([^}]*)\}", lazy)
    assert rule, "the .ocr-card rule moved"
    selector, body = rule.group(1), rule.group(2)
    assert "width: min(96vw" in body
    assert ":not(.sheet-card-page)" in selector, (
        "the lazy desktop size would override the phone page (loads later)"
    )
