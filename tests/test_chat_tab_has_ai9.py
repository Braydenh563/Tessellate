"""The chat tab carries no `:has()` on its roots (AI9, audit 1031).

A `:has()` whose subject is `#tab-chat` or a `.tab-main` is re-checked for every
change under it: a send and its answer made 230 style invalidations on the tab
and 190 on its column, and Settings-sized pages pay the same. The two rules
that did it read a class now, set where the panel opens and closes."""

from __future__ import annotations

import re

from tests._app_js import app_js_text
from tests.test_ui_recipes import ROOT

CSS = (ROOT / "frontend" / "css" / "04-chat-dock-appearance.css").read_text(encoding="utf-8")


def test_no_has_on_the_chat_tab_or_its_column():
    assert not re.search(r"#tab-chat(?:\s+\.layout\s*>\s*\.tab-main)?:has\(", CSS)
    assert not re.search(r"\.tab-main:has\(#(?:web-panel|note-picker-panel)", CSS)


def test_the_classes_the_rules_read_are_set_where_the_panels_open_and_close():
    js = app_js_text()
    assert '.tab-main.web-open>#chat-main' in CSS and 'closest(".tab-main")?.classList.toggle("web-open", show)' in js
    assert "#tab-chat.note-picker-open .msg-actions" in CSS
    assert js.count("note-picker-open") >= 2
