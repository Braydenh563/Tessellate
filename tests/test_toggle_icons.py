"""A toggle shows its state in its glyph (INBOX 904 B58, second half).

Owner: "across the app, there are quite a few instances where clicking an icon
button to toggle smth doesn't change the icon's look". The Documents width,
dim and typewriter toggles painted a fill and a tooltip only.
"""

from tests._app_js import JS_DIR


def test_document_reading_toggles_swap_their_glyph():
    code = (JS_DIR / "documents.js").read_text(encoding="utf-8")
    assert "function docToggleIcon(button, on, onIcon, offIcon)" in code
    for pair in (
        '"ph-arrows-in-line-horizontal", "ph-arrows-out-line-horizontal"',
        '"ph-drop-half-bottom", "ph-drop-half"',
        '"ph-arrows-in-line-vertical", "ph-arrows-down-up"',
    ):
        assert "docToggleIcon(" in code and pair in code, pair
