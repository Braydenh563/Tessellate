"""INBOX 1547: a rendered block stays drawn while a selection crosses it.

A drag from above a diagram to below it toggled every widget it crossed and
moved the text below by 147px (scratchpad/ui-sweeps/flicker1547.js against
the old code: 12 of 12 steps); now 0 toggles and 0px. The rule: a widget
shows its source only while a selection starts in it (`docLiveSpanTouched.anchorIn`).
"""
import re

from tests._app_js import frontend_text

CM = frontend_text("documents-cm.js")
DOCS = frontend_text("documents.js")
MERMAID = frontend_text("documents-mermaid.js")


def test_every_replacing_widget_uses_the_anchor_rule() -> None:
    for widget in ("DocTocWidget", "DocCommentWidget", "DocMathWidget", "DocIconWidget", "DocEmbedWidget"):
        for m in re.finditer(rf"widget: new {widget}\b", CM):
            before = CM[max(0, m.start() - 900): m.start()]
            last = max(before.rfind("rangeRevealed("), before.rfind("widgetRevealed("))
            assert last >= 0 and before[last:].startswith("widgetRevealed("), widget


def test_the_mermaid_field_and_the_redraw_check_share_it() -> None:
    assert "docLiveSpanTouched.anchorIn(state.selection.ranges, block.from, block.to)" in MERMAID
    same = DOCS.split("function docLiveRevealSame(", 1)[1].split("\n}\n", 1)[0]
    assert "v & 2 ? docLiveSpanTouched.anchorIn : docLiveSpanTouched" in same
    assert "range.anchor >= from && range.anchor <= to" in DOCS
