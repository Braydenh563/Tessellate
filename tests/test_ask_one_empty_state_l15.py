"""Notes, Ask with no model shows one empty state, not two (L-chat-15).

The first-run walk (scratchpad/first-run-472.md row 10), measured again
2026-11-13 at 390 on the current tree: the no-model notice and its "Try
asking" chips at y=440 to 705, then "Ask your own notes a question" with its
own two sentences at y=715. The notice already says what Ask does with no
model, so the idle card steps aside while the notice is shown and comes back
when it is dismissed or a model connects.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_the_idle_card_follows_the_offline_notice_in_the_markup():
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    ask = html[html.index('id="ask-offline"') :]
    assert ask.index('id="ask-idle"') > 0


def test_the_idle_card_hides_while_the_notice_shows():
    css = (ROOT / "frontend" / "css" / "07-whiteboard-misc.css").read_text(encoding="utf-8")
    rule = re.search(r"#ask-offline:not\(\.hidden\)\s*~\s*\.ask-idle\s*\{([^}]*)\}", css)
    assert rule and "display: none" in rule.group(1)
