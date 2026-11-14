"""The document outline is not rebuilt when no heading changed (INBOX 424).

`renderDocOutline` runs on every pause in the typing. Rebuilding every row
and re-marking the current one (two forced layouts in
`keepOutlineRowInView`) cost 515ms of a 40-character burst at 4x CPU in a
16-heading document; with the rows kept it is 12ms. The key has to hold
everything a row is drawn from, or a renamed heading would keep its old row.
"""

from pathlib import Path
from tests._app_js import documents_text

ROOT = Path(__file__).resolve().parent.parent


def _render_outline() -> str:
    src = documents_text()
    start = src.index("function renderDocOutline() {")
    return src[start : src.index("\n}\n", start)]


def test_the_outline_keeps_its_rows_when_the_key_is_unchanged():
    body = _render_outline()
    guard = body.index("outlineKey === docOutlineKey")
    assert guard < body.index("list.replaceChildren()")


def test_the_key_holds_everything_a_row_is_drawn_from():
    body = _render_outline()
    key = body[body.index("const outlineKey") : body.index("if (outlineKey === docOutlineKey")]
    for part in ("h.level", "h.line", "h.text", "h.tasks", "needle", "folds", "row.shown", "row.foldable"):
        assert part in key, part
