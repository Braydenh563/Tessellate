"""L529, boards driven: `<sheet-host>` says it keeps a dialog's `open`, but
only the property was kept, so `#wb-template-dialog[open]` (two board sweeps,
and any `[open]` rule) never matched an open sheet and the Present and board
sweeps timed out at their first step. The attribute follows the property."""

from __future__ import annotations

from tests._app_js import app_js_text


def test_the_open_attribute_follows_the_sheet():
    text = app_js_text()
    start = text.index('customElements.define("sheet-host"')
    body = text[start : start + 1600]
    assert 'this.toggleAttribute("open", true)' in body
    assert 'this.removeAttribute("open")' in body
