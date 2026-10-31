"""A web result's snippet marks the words the search was for (BACKLOG section
13, "result cards worth reading, not just clicking").

The card already had the domain mark, the host, the engines that found it and a
title that opens the reader; the one piece left was the snippet with the matched
terms highlighted. `webQueryTerms` (chat.js) turns the query into the words
worth marking, and `buildWebResultRow` hands them to `highlightInto`
(notes-list.js), which builds `<mark>` nodes rather than markup, so a snippet
from the open web is still never parsed as HTML. The DOM half is measured by
`scratchpad/ui-sweeps/bl1005-webhighlight.js`.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CHAT = (ROOT / "frontend" / "js" / "web-results.js").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "css" / "03-dashboard-widgets.css").read_text(encoding="utf-8")


def _terms(query: str) -> list[str]:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    start = CHAT.index("const WEB_TERM_STOP_WORDS")
    end = CHAT.index("const webResultTerms")
    script = CHAT[start:end] + f"\nconsole.log(JSON.stringify(webQueryTerms({json.dumps(query)})));\n"
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip())


def test_the_terms_are_the_queries_own_words_lowercased():
    assert _terms("SQLite WAL mode") == ["sqlite", "wal", "mode"]


def test_little_words_and_fragments_are_not_marked():
    assert _terms("what is the best way to use it") == ["best", "way", "use"]
    assert _terms("a b to of") == []


def test_a_repeated_word_is_marked_once_and_punctuation_splits_words():
    assert _terms("bread, bread; rolls-and-buns") == ["bread", "rolls", "buns"]


def test_letters_beyond_ascii_are_words():
    assert _terms("Zürich über naïve") == ["zürich", "über", "naïve"]


def test_an_empty_query_marks_nothing():
    assert _terms("") == []
    assert _terms("   ") == []


def test_every_row_marks_the_same_terms_including_show_more():
    # The terms are set once, before the first row is built, so the rows that
    # "Show more" reveals later are marked the same way.
    assert CHAT.index("webResultTerms.splice(0, webResultTerms.length, ...webQueryTerms(query))") < CHAT.index(
        "for (const result of results.slice(0, INITIAL_SHOWN))"
    )
    row = CHAT[CHAT.index("function buildWebResultRow") :]
    row = row[: row.index("\n}\n")]
    assert "highlightInto(snippet, result.snippet, webResultTerms)" in row
    # Never `innerHTML`: a snippet is text from the open web.
    assert "innerHTML" not in row


def test_the_mark_has_the_apps_own_wash_not_the_browsers_yellow():
    rule = CSS[CSS.index(".web-result-snippet mark") :]
    rule = rule[: rule.index("}")]
    assert "var(--accent-soft)" in rule
    assert "color: inherit" in rule
