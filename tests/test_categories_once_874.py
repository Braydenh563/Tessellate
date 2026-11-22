"""L-world-class-874: boot fetched /categories twice, once at the notes list's
first page and again at its last. The list is the server's whole list, not the
loaded pages', so one read a load is enough: at the first page."""

from __future__ import annotations

import re

from tests._app_js import app_js_text


def _load_entries_body() -> str:
    text = app_js_text()
    start = text.index("async function _loadEntries(")
    end = text.index("\n}\n", start)
    return text[start:end]


def test_a_load_reads_the_categories_once_at_its_first_page():
    body = _load_entries_body()
    calls = re.findall(r"^\s*(.*)\bloadCategories\(\)", body, flags=re.M)
    assert calls == ["if (first) "], calls
