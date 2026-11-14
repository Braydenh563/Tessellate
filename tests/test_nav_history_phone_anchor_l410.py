"""Source text: layout and placement are measured in a browser the suite does not run (probe numbers below); the rule is held as its CSS or JS text. L410: Recent places opened from the phone bar's sheet anchors to Back.

Measured at 390 (probe nh.js): the bar's history button has no box there, so
the menu went to x=0 with an inline bottom of 848px. Anchored to Back it lands
at 81,54, under the header, where the long press puts it."""

from tests._app_js import app_js_text


def test_an_undrawn_opener_falls_back_to_back():
    """Source text: openNavHistoryMenu swaps a boxless anchor for #status-back."""
    js = app_js_text()
    body = js.split("async function openNavHistoryMenu(anchorEl) {", 1)[1].split("\n}\n", 1)[0]
    assert 'if (!anchorEl?.getClientRects().length) anchorEl = $("status-back")' in body
    assert body.index('$("status-back")') < body.index("anchorEl.getBoundingClientRect()")
