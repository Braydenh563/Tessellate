"""INBOX 1696 o, the owner: "elsewhere in you notebook stuff appears above the ask next stuff, but the
why this answer stuff appears below, also their visual style of the buttons doesn indicate that they
are a dropdown and different from the ask next stuff"."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_every_ask_part_opens_above_ask_next():
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    foot = html[html.index('id="ask-answer-foot"') :]
    foot = foot[: foot.index("</div>\n              </div>")]
    order = re.findall(r'id="(ask-[a-z-]+)"', foot)
    assert order[-1] == "ask-followups", order
    for part in ("ask-answer-related", "ask-answer-sources", "ask-insights", "ask-why"):
        assert order.index(part) < order.index("ask-followups"), order


def test_a_foot_chip_carries_the_folds_caret_turned_by_aria_expanded():
    css = (ROOT / "frontend" / "css" / "answer-foot-lazy.css").read_text(encoding="utf-8")
    closed = re.search(r"\.answer-foot-chip::after \{([^}]*)\}", css)
    assert closed and '"\\e136"' in closed.group(1) and "rotate(-90deg)" in closed.group(1)
    assert re.search(r'\.answer-foot-chip\[aria-expanded="true"\]::after \{\s*transform: none;', css)
    assert ':root[data-motion="reduced"]) .answer-foot-chip::after' in css
