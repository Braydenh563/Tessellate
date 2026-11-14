"""Source text: the background librarian's review is Settings DOM a browser
presses; the source pins the whole-pass discard (L-ui-modernisation-73).

A true dry run cannot be had (`ai/autonomous.py` `_last_pass`: the model picks
each call from the last result), so the pass is reviewed after: each change
shows its diff and its own Undo, and now the pass as a whole is kept (Keep
all) or discarded (Undo all, every change's undo, last first).
"""

from __future__ import annotations

from pathlib import Path

from tests._app_js import frontend_text

ROOT = Path(__file__).resolve().parent.parent


def test_the_review_offers_keep_all_and_undo_all():
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    start = html.index('id="autonomous-review"')
    box = html[start : html.index("</div>\n                </div>", start)]
    assert 'id="autonomous-review-undo-all"' in box and ">Undo all<" in box
    assert ">Keep all<" in box


def test_undo_all_presses_each_rows_undo_last_first():
    source = frontend_text("settings-controls.js")
    start = source.index('$("autonomous-review-undo-all")')
    body = source[start : source.index("});\n", start)]
    assert "[data-change-undo]" in body and ".reverse()" in body
    assert "confirmDialog(" in body
