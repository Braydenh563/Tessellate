"""L-documents-54: the Library Documents row's page (heading and opening lines), from the list's own summary."""

from __future__ import annotations

from pathlib import Path

import pytest

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


def test_the_summary_names_the_first_embedded_picture_as_the_cover() -> None:
    """L-documents-80: no second request per row; the list's own summary carries it."""
    from tessellate.api.routes_documents import _cover

    body = "# Trip\n\n![A river|400|center](/media/river.jpg) and ![](/media/second.png)\n"
    assert _cover(body) == "/media/river.jpg"
    assert _cover("![diagram](/media/a_b-1.png \"title\")") == "/media/a_b-1.png"
    assert _cover("plain words, ![[note]] and [a link](/media/x.pdf)") == ""
    assert _cover("![far](https://example.com/x.png)") == ""
    assert _cover("") == ""


class _Tally(str):
    """A string that counts the characters each find or rfind walks over (to its hit, or across its whole range on a miss)."""

    walked = 0

    def _span(self, sub, start, end, hit, back):
        start = 0 if start is None else start
        end = len(self) if end is None else end
        _Tally.walked += (end - start) if hit == -1 else (end - hit if back else hit + len(sub) - start)
        return hit

    def find(self, sub, start=None, end=None):
        return self._span(sub, start, end, str.find(self, sub, start, end), False)

    def rfind(self, sub, start=None, end=None):
        return self._span(sub, start, end, str.rfind(self, sub, start, end), True)


@pytest.mark.parametrize(
    "text",
    ["![" * 50_000, "![" * 50_000 + "](/media/x.png)", "](/media/x " * 20_000, "![a](/media/" * 20_000, "![" * 50_000 + "]" + "(" * 1000],
)
def test_the_cover_scan_is_linear_on_repeated_openers(text) -> None:
    """CodeQL 2305: an alt pattern searched from each "![" was quadratic on 100k characters of "![".

    The proof is the characters scanned, not a wall clock: at most five characters scanned per character (three
    look-backs, each over the span since the last hit, and the forward step), and twice the text costs twice the scan, where the old search grew fourfold.
    """
    from tessellate.api.routes_documents import _cover

    walked = []
    for times in (1, 2):
        _Tally.walked = 0
        _cover(_Tally(text * times))
        walked.append(_Tally.walked)
    assert walked[0] <= 5 * len(text)
    assert walked[1] <= 2.01 * walked[0]


def test_the_page_card_draws_the_cover_lazily_in_the_same_box() -> None:
    js = frontend_text("library.js")
    block = js[js.index('page.className = "doc-list-page"') :][:2000]
    assert "doc.cover" in block
    assert 'loading = "lazy"' in block
    assert "apiJson" not in block
    css = (Path(__file__).resolve().parent.parent / "frontend" / "css" / "library-lazy.css").read_text()
    rule = css[css.index(".doc-list-page-cover {") :][:400]
    assert "object-fit: cover" in rule
    assert "inline-size: 100%" in rule and "block-size: 100%" in rule
