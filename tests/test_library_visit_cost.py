"""A Library visit does not start the grammar checker (audit 2026-10-05, FE-03).

Measured before: one click on Library fetched `harper-worker.js`, the 15.9 MB
grammar WASM and the 871 KB word list, because `documents.js`'s last line
paints the document tools once at load (`renderDocTools()`), with no document
open, and that pass asked for both. The browser half of this is
`scratchpad/ui-sweeps/fe1005-libreq.js` (Library visit: none of the three;
opening a document with text: all three, and findings). This holds the two
guards that make it so, because Python cannot click a tab.
"""

from __future__ import annotations
from tests._app_js import frontend_text

import re
from pathlib import Path

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"


def _function(file: str, name: str) -> str:
    text = frontend_text(file)
    start = text.index(f"function {name}(")
    end = text.index("\n}\n", start)
    return text[start:end]


def test_the_grammar_checker_is_not_asked_about_an_empty_editor():
    body = _function("documents-prose.js", "docGrammarRequest")
    first = body.split("\n")[1].strip()
    assert re.match(r"if \(!text \|\| !text\.trim\(\)\) return;", first), first


def test_the_word_list_is_not_fetched_for_an_empty_editor():
    body = _function("documents-prose-check.js", "docProseFindings")
    calls = [line.strip() for line in body.split("\n") if "docLoadWordlist()" in line]
    assert calls == ["if (text.trim()) docLoadWordlist();"], calls


def test_the_load_time_paint_is_still_there():
    """The status bar is painted at load so it is not blank before the first
    keystroke; only the checkers wait for text."""
    text = frontend_text("documents.js")
    assert re.search(r"^renderDocTools\(\);$", text, re.M)
