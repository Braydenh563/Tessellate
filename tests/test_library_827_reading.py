"""Source text: the behaviour is CSS and front-end script that only a browser renders, and pytest has none, so these pin the rules' text.

INBOX 827 L1 and L2: the Files row's reading column, and the Recordings empty state.

Static checks of what the sweep measured (`l12.js` at 1440: column 448px = 50vh cap, 16px type on a
25.6px line, a Page N mark per page, find at 112 matches, a transparent summary; the empty state
has Record and Import audio).
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(*parts: str) -> str:
    return (ROOT.joinpath(*parts)).read_text()


def test_reading_column_is_body_size_and_fades():
    css = _read("frontend", "css", "library-lazy.css")
    block = re.search(r"\.library-file-reading-text \{([^}]*)\}", css).group(1)
    assert "font-size: var(--text-body)" in block
    assert "line-height: 1.6" in block
    assert "50vh" in block
    assert re.search(r"\.library-file-reading-text:not\(\.is-at-end\) \{\s*mask-image", css)


def test_disclosure_row_is_quiet():
    css = _read("frontend", "css", "library-lazy.css")
    m = re.search(r"\.library-file-rows \.library-image-reading > summary:not\(\.icon-only\):not\(\.icon-button\) \{([^}]*)\}", css)
    assert m and "background: transparent" in m.group(1) and "border-color: transparent" in m.group(1)


def test_pages_join_with_a_form_feed_and_the_row_marks_them():
    server = _read("src", "tessellate", "api", "routes_files_ocr.py")
    assert '"\\n\\n\\f\\n\\n".join(parts)' in server
    js = _read("frontend", "js", "library.js")
    assert 'split("\\f")' in js and "Page ${index + 1}" in js
    assert 'replace(/\\f/g, "")' in js, "Copy text must not carry the page separators"


def test_find_box_only_when_the_text_scrolls():
    js = _read("frontend", "js", "library.js")
    #: The builder lives in library-links.js, loaded with library.js (global-scope cap).
    assert "function buildReadingFind(" in _read("frontend", "js", "library-links.js")
    assert "LinkShelf.readingFind(fullText)" in js
    assert "scrollHeight > fullText.clientHeight + 1" in js
