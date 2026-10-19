"""INBOX 1322a: a Format button beside Library in the whiteboard top bar."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_format_button_beside_library_and_wired():
    html = (ROOT / "frontend/index.html").read_text()
    lib = html.index('id="wb-add-note"')
    fmt = html.index('id="wb-format-btn"')
    assert 0 < fmt - lib < 600
    js = (ROOT / "frontend/js/whiteboard-format.js").read_text()
    assert 'on("wb-format-btn", "click", () => wbFormatToggle())' in js
    assert "wbFmtMarkButton(true)" in js and "wbFmtMarkButton(false)" in js


def test_format_button_in_help():
    from tessellate.ai import help_chat

    body = next(t["body"] for t in help_chat.HELP_TOPICS if t["id"] == "board-format")
    assert "top bar's Format button" in body
    cmds = (ROOT / "frontend/js/whiteboard-commands.js").read_text()
    assert "top bar button" in cmds
