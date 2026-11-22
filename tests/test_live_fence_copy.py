"""Live view: a fenced block carries a Copy button that cannot trap the caret.

L-documents-65 (DOCUMENTS_PLAN section 15's two objections): the control is a
widget with `ignoreEvent` true and no text, and it is laid over the first code
line so the 8px fence row stays 8px. Drive numbers are in HISTORY.md.
"""

from __future__ import annotations

import re

from tests._app_js import documents_text

TEXT = documents_text()


def _widget() -> str:
    match = re.search(r"class DocFenceCopyWidget extends WidgetType \{.*?\n  \}\n", TEXT, re.S)
    assert match, "DocFenceCopyWidget not found"
    return match.group(0)


def test_widget_is_inert_to_the_caret_and_has_no_text():
    body = _widget()
    assert re.search(r"ignoreEvent\(\)\s*\{\s*return true", body)
    assert re.search(r"ignoreMutation\(\)\s*\{\s*return true", body)
    assert 'contentEditable = "false"' in body
    assert "aria-label" in body and "ph:copy" in body
    assert "textContent" not in body, "text in the widget could ride a selection"


def test_copy_reads_the_code_without_fences_at_click_time():
    body = _widget()
    assert "copyToClipboard(" in body and "FencedCode" in body
    assert "open.to + 1" in body and "last.from - 1" in body


def test_it_is_placed_on_the_first_code_line_not_a_new_row():
    assert "new DocFenceCopyWidget()" in TEXT
    assert "line.number === first.number + 1" in TEXT


def test_it_is_an_overlay_with_a_touch_hit_area():
    theme = TEXT[TEXT.index('".cm-md-fence-copy": {') :]
    rule = theme[: theme.index("},")]
    assert 'position: "absolute"' in rule
    assert '".cm-md-fence-copy.is-touch::after"' in theme
    assert '"44px"' in theme[: theme.index('".cm-md-fence-copy.is-touch::after"') + 400]
