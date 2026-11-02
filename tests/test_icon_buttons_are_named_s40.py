"""A button with no words in the page has an `aria-label`, not a title alone
(audit 1028 S40).

A `title` is a tooltip: it is not read by every screen reader and is never
shown on touch. Measured in the running app at 1280 on the seven tabs
(dashboard, notes, chat, graph, library, timeline, reminders): every visible
button, summary, link and tab has either text or an `aria-label`, 0 of them
named by `title` alone. The buttons in index.html that are drawn empty and named
by script at runtime are the allowlist below; a new icon-only button written
into index.html names itself.
"""

from __future__ import annotations

import re
from pathlib import Path

INDEX = Path(__file__).resolve().parents[1] / "frontend" / "index.html"

#: Empty in the markup, named (text or aria-label) by the script that fills
#: them: the status bar's buttons and the four chips below.
FILLED_BY_SCRIPT = {
    "chat-active-model", "chat-context", "timeline-month-btn", "graph-layout-chip", "logs-copy",
    *{f"status-{name}" for name in ("notes", "reminders", "task", "timer", "activity", "command", "agent", "guide", "find", "back", "forward", "undo", "redo")},
}


def test_an_empty_button_in_the_page_has_an_aria_label_or_is_named_by_its_script():
    html = re.sub(r"<!--.*?-->", "", INDEX.read_text(encoding="utf-8"), flags=re.S)
    unnamed = []
    for match in re.finditer(r"<button\b([^>]*)>(.*?)</button>", html, flags=re.S):
        attrs, inner = match.groups()
        if re.sub(r"<[^>]+>", "", inner).strip() or re.search(r"aria-label(?:ledby)?=", attrs):
            continue
        ident = re.search(r'\bid="([^"]+)"', attrs)
        if ident and ident.group(1) in FILLED_BY_SCRIPT:
            continue
        unnamed.append((ident.group(1) if ident else attrs.strip()[:70]))
    assert not unnamed, f"icon-only buttons with a title at most: {unnamed}"
