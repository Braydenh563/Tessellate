"""A long message of yours keeps a reading width (the owner, 2026-11-03: "long user chat
message bubbles go the full screen width and arent kept to a proper max width")."""

from __future__ import annotations

import re
from pathlib import Path

CSS = (Path(__file__).resolve().parents[1] / "frontend" / "css" / "02-chat-graph.css").read_text(encoding="utf-8")


def test_a_user_bubble_has_a_max_width_under_the_answers():
    rule = re.search(r"\n\.msg\.user \{(.*?)\n\}", CSS, re.S).group(1)
    assert "max-width: min(72%, 42rem)" in rule
    assert "max-width: 82%" in CSS, "the answer's cap the user's stays under"
