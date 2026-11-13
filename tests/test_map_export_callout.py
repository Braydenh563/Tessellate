"""A map's SVG and PNG export draws a topic's callout and labels (L377).

Driven in the app (a callout and two labels on one topic): the exported SVG held none of the
words before; now each is placed from its live box in the card. Source pattern, since the
export reads computed boxes.
"""
from tests._app_js import JS_DIR


def test_map_export_draws_callout_and_label_chips():
    js = (JS_DIR / "whiteboard.js").read_text(encoding="utf-8")
    assert 'cardEl.querySelector(".wb-map-callout")' in js
    assert 'cardEl.querySelectorAll(".wb-map-tags .wb-map-tag")' in js
    assert "wordsY: words ? inCard(words).y : null" in js and "labelTop = callout.wordsY + 15" in js  # read in wbExportLook (topicExtras), drawn by the builder
