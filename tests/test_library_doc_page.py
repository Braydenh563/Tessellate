"""L-documents-54: the Library Documents row's page (heading and opening lines), from the list's own summary."""

from __future__ import annotations

from tests._app_js import frontend_text


def test_the_page_is_drawn_from_the_title_and_the_preview_the_list_already_has() -> None:
    js = frontend_text("library.js")
    block = js[js.index('page.className = "doc-list-page"') :][:1200]
    assert "leafHead.textContent = doc.title" in block
    assert "leafLines.textContent = docPreview" in block
    # No second request per row: the summary's `preview` is all it uses.
    assert "apiJson" not in block


def test_the_server_still_sends_a_flattened_opening() -> None:
    from tessellate.api.routes_documents import PREVIEW_CHARS, _preview

    text = _preview("# Trail plan\n\nFirst we list the **gear**.\n\n- tent\n- stove\n\n" + "word " * 200)
    assert text.startswith("Trail plan \u00b7 First we list the gear")
    assert len(text) <= PREVIEW_CHARS + 1
