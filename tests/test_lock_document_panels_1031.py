"""Locking left the document's words on the page and the AI panel over the lock
screen (audit 1031 DC1, DC2).

After `lockNow()` the editor was emptied, but the AI diff (1,385 characters), the
replace list, the outline, the crumbs, both document lists, the prose panel and
the dashboard's recent-documents card kept the words, and a non-modal
`#doc-ai-panel` sat above the lock overlay (z-index 2100 against 50): the element
under the Unlock button was the panel's own input. The class fix is a marker,
`data-holds-notebook`, so a new panel is covered by default, and every open panel
put away while the overlay shows."""

from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path

from tests._app_js import app_js_text

HTML = (Path(__file__).resolve().parent.parent / "frontend" / "index.html").read_text(encoding="utf-8")

#: Each of these held the document's words while locked (DC1).
MARKED = [
    "doc-ai-diff",
    "doc-ai-diff-head",
    "doc-ai-result",
    "doc-ai-instruction",
    "doc-ai-scope",
    "doc-replace-list",
    "doc-replace-summary",
    "doc-outline",
    "doc-outline-filter",
    "doc-list",
    "doc-prose-panel",
    "doc-preview",
    "chat-input",
    "dash-grid",
]


class _Marked(HTMLParser):
    VOID = {"input", "br", "img", "hr", "meta", "link", "source", "col", "wbr"}

    def __init__(self) -> None:
        super().__init__()
        self.stack: list[tuple[str, bool]] = []
        self.marked: list[dict] = []
        self.static_inside: list[tuple[str, str]] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        inside = any(m for _t, m in self.stack)
        if inside and a.get("id"):
            self.static_inside.append((a["id"], tag))
        mark = "data-holds-notebook" in a
        if mark:
            self.marked.append({"id": a.get("id"), "class": a.get("class", ""), "tag": tag})
        if tag not in self.VOID:
            self.stack.append((tag, mark))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break


def _walk() -> _Marked:
    w = _Marked()
    w.feed(HTML)
    return w


def test_every_document_panel_that_holds_words_is_marked():
    ids = {m["id"] for m in _walk().marked}
    assert [i for i in MARKED if i not in ids] == []
    assert any("doc-crumbs-list" in m["class"] for m in _walk().marked), "the crumbs list holds the title"


def test_a_marked_container_holds_no_static_ui():
    """Purging deletes children: a marked container may hold only what the app
    renders into it (INBOX 492)."""
    assert _walk().static_inside == []


def test_the_purge_clears_every_marked_element():
    js = app_js_text()
    start = js.index("function purgeLockedContent(")
    body = js[start : js.index("\n}\n", start)]
    assert "[data-holds-notebook]" in body
    assert "input, textarea" in body and ".value" in body


def test_open_panels_are_put_away_while_the_overlay_shows():
    """DC2: a non-modal `role=dialog` panel (the AI panel is one) is closed under
    the lock screen, not only `dialog:modal` and popovers."""
    js = app_js_text()
    start = js.index("const lockStash")
    block = js[start : js.index(".observe($(\"lock-overlay\")", start)]
    assert ".modal-overlay:not(.hidden)" in block
    assert "[role=dialog]:not(.hidden)" in block
    assert '"prompt"' in block, "a prompt over live work gives the panels back after it"
