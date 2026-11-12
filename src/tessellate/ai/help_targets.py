"""The control a tab-level Guide topic rings when its button is pressed (L51).

A topic whose badge names only a tab used to land on the tab's one main control
(`GUIDE_TAB_LANDING` in help-chat.js), so "How do I tidy my notes?" and "Where is
the note history?" lit the same box. Here each topic that has a control of its
own names it, as the element id (several, space separated, are tried in order,
the first on screen is lit). A topic with no id here lives inside an editor, a
canvas or an answer, which has no control on the tab itself: it keeps the tab's
landing. `tests/test_help_targets_l51.py` checks every id is in `index.html`.
"""

from __future__ import annotations

TARGETS: dict[str, str] = {
    "voice": "mic-note",
    "search": "note-search",
    "tags-categories": "entry-tags entry-category",
    "count-words": "entry-count",
    "quick-note": "capture-bar-input",
    "attachments": "entry-attach-file",
    "filing": "entry-category",
    "tidy": "notes-tidy",
    "notes-list": "entry-list",
    "card-content": "notes-view-cards",
    "chat-list": "chat-sidebar",
    "queued-messages": "chat-send",
    "notifications": "notif-btn",
    "statistics": "dash-grid",
    "first-steps": "dash-first-steps",
    "graph-display": "graph-options-toggle",
    "graph-options-help": "graph-options-toggle",
    "quick-add": "reminder-magic",
}


def apply(topics: list[dict]) -> None:
    """Give each tab-only badge in `topics` its own control, where `TARGETS` names one."""
    for topic in topics:
        badge = topic.get("badge") or {}
        target = TARGETS.get(topic.get("id") or "")
        if target and badge.get("tab") and not badge.get("target"):
            topic["badge"] = {**badge, "target": target}
