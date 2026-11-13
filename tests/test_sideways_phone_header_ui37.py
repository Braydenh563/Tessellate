"""Source text: "Sideways phone: tab strip wraps by 4.1px at 844x390."

L-ui-modernisation-37. Measured at 844x390 touch: the logo (28px), the space
switcher (62.6), the tabs (413.8), the controls (298.2) and three header gaps
of 7.2 (`--space-4`) needed 824.2px of the 820 inside the bar's padding, so
the strip wrapped and the header was 108px of 390. With the gaps at
`--space-2`, the step the band below 820 already uses, it is one row, 56px."""

import re
from pathlib import Path

CSS = Path(__file__).resolve().parents[1] / "frontend" / "css"


def _header_gap(text: str, media: str) -> str:
    block = text[text.index(media) :]
    rule = re.search(r"header#top-bar\s*\{([^}]*)\}", block)
    assert rule, media
    return re.search(r"(?<![-\w])gap:\s*([^;]+);", rule.group(1)).group(1).strip()


def test_the_bar_below_940_spaces_its_items_like_the_band_below_820() -> None:
    tokens = (CSS / "00-tokens-shell.css").read_text(encoding="utf-8")
    responsive = (CSS / "10-responsive.css").read_text(encoding="utf-8")
    below_820 = _header_gap(responsive, "@media (min-width: 600px) and (max-width: 819.98px) {")
    assert below_820 == "var(--space-2)"
    assert _header_gap(tokens, "@media (max-width: 940px) {") == below_820
