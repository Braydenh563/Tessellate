"""Bidi control characters never reach a preview or a title (audit 1029 N20).

U+202E and its kin reorder what follows them on screen, so a note could show
a preview or title that reads differently from its words. They are stripped
where a note is turned into a label; the stored text keeps them.
"""

from __future__ import annotations

import pytest

from tessellate.api import routes_entries, routes_graph
from tessellate.entry import manager
from tests._app_js import app_js_text

CONTROLS = ["‪", "‫", "‬", "‭", "‮", "⁦", "⁧", "⁨", "⁩"]


@pytest.mark.parametrize("mark", CONTROLS)
def test_server_labels_drop_every_bidi_control(mark):
    text = f"# Pay {mark}rtl{mark} bill\n\nbody {mark}words"
    assert mark not in (manager.extract_title(text) or "")
    assert mark not in routes_entries._preview(text)
    assert mark not in routes_graph._preview(text)
    assert manager.extract_title(text) == "Pay rtl bill"


def test_the_client_preview_drops_them_too():
    js = app_js_text()
    body = js[js.index("function notePreviewText(") :][:400]
    assert "\\u202a-\\u202e\\u2066-\\u2069" in body
