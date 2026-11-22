"""L-world-class-870: the import preview built a thousand rows in one task
(125 to 229 ms idle, 1.1 s loaded). It builds a screenful, then a hundred a
frame, and the ticks live in an array, so Import and Select all are right
before the last row lands."""

from __future__ import annotations

from tests._app_js import frontend_text


def _fn(text: str, name: str) -> str:
    start = text.index(f"function {name}(")
    return text[start : text.index("\n}\n", start)]


def test_rows_land_in_chunks_and_the_ticks_are_not_read_off_the_boxes():
    body = _fn(frontend_text("app-import.js"), "importPreview")
    assert "const ticked = rows.map((row) => !row.already);" in body
    assert "requestAnimationFrame(() => append(to, to + IMPORT_PREVIEW_CHUNK))" in body
    assert "append(0, IMPORT_PREVIEW_FIRST);" in body
    assert "rows.forEach(" not in body, "every row at once was the long task"
    assert "!ticked[at]" in body and "boxes[at].checked" not in body, "Import reads rows not built yet"
    assert "ticked.fill(on);" in body
