"""`select.focus()` reaches the opener (DOCUMENTS_PLAN, enhanceSelect found-open).

`enhanceSelect` takes the native `<select>` out of the tab order and draws a
`<button>` opener, so `select.focus()` used to focus nothing (measured:
`document.activeElement` stayed `<body>`). The select now forwards `focus` to
its opener. `tests/test_select_focus.py` still keeps new code off key
listeners on a select, which a forward cannot fix."""

from __future__ import annotations

from tests._app_js import frontend_text


def test_an_enhanced_selects_focus_goes_to_its_opener():
    src = frontend_text("sheets-selects.js")
    body = src[src.index("function enhanceSelect(select) {") :][:9000]
    assert "select.focus = (options) => opener.focus(options);" in body
