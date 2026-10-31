"""Audit 1029 row 44 (N8): what a note card draws for a table and a code fence.

A pipe table and a fenced code block in a note showed as raw source in its card,
where a document, Chat and the Read view draw them. One rule now: a card renders
the same safe markdown subset as everywhere else, by handing the block to
`renderMarkdown` (`mdBlockEnd` finds where it ends).

The line finder runs in node; the rest is source checks, since the drawing needs
a browser (numbers in the commit, from scratchpad/ui-sweeps).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"

node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not available")


def _decl(path: str, name: str) -> str:
    text = (JS / path).read_text(encoding="utf-8")
    start = re.search(rf"^function {name}\(", text, re.M).start()
    return text[start : text.index("\n}\n", start) + 2]


def _run(script: str) -> object:
    done = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30, check=True)
    return json.loads(done.stdout)


@node
def test_a_block_end_is_found_for_a_fence_and_a_table_only() -> None:
    source = "\n".join(_decl("markdown.js", n) for n in ("isTableSeparator", "splitTableRow", "mdBlockEnd"))
    cases = {
        "fence": ["a", "```js", "x = 1", "```", "b"],
        "open_fence": ["```", "x", "y"],
        "table": ["| a | b |", "|---|---|", "| 1 | 2 |", "| 3 | 4 |", "", "after"],
        "table_to_end": ["a | b", "--|--", "1 | 2"],
        "no_separator": ["| a | b |", "plain"],
        "plain": ["just words"],
        "pipe_in_prose": ["a | b", "more words"],
    }
    probes = {"fence": 1}
    script = (
        source
        + f"\nconst cases = {json.dumps(cases)}, at = {json.dumps(probes)};"
        + "\nconsole.log(JSON.stringify(Object.fromEntries(Object.keys(cases).map(k => [k, mdBlockEnd(cases[k], at[k] || 0)]))));"
    )
    ends = _run(script)
    assert ends["fence"] == 4  # the line after the closing fence
    assert ends["open_fence"] >= 3  # an unclosed fence runs to the end, as renderMarkdown reads it
    assert ends["table"] == 4  # stops at the blank line
    assert ends["table_to_end"] == 3
    assert ends["no_separator"] == 0
    assert ends["plain"] == 0
    assert ends["pipe_in_prose"] == 0


def test_the_card_hands_a_block_to_the_page_renderer() -> None:
    body = _decl("notes-list.js", "renderNoteText")
    assert "mdBlockEnd(lines, i)" in body
    assert "renderMarkdown(" in body
    # The block is a box of its own, so the clamp and the card's width treat it like a callout.
    assert "entry-md-block" in body


def test_the_card_prose_changes_skip_a_fence() -> None:
    """The heading hashes and list dashes the card strips are source in a code fence."""
    cards = (JS / "note-cards.js").read_text(encoding="utf-8")
    fill = cards[cards.index("const fillContent = () => renderNoteText(") :]
    fill = fill[: fill.index("fillContent();")]
    # The strip is passed to renderNoteText as the prose step, after the terms, not run over the whole note first.
    assert fill.index("searchHighlightTerms()") < fill.index("{1,6}[ \\t]+/gm")
    text = _decl("notes-list.js", "renderNoteText")
    assert "prose(" in text
    assert "terms, prose)" in text  # a column keeps the same step


def test_a_plain_quote_draws_as_a_quote_on_a_card() -> None:
    """Audit 1031 N26: "> quote" and ">> nested" showed as typed on a card while the
    callout beside them was drawn. The card hands the quote to `mdQuoteElement` (the
    document view's builder) and refills its body through itself, so a nested quote
    nests and the search words stay marked. Measured in the app: a 3px bar, 12.8px
    inset, the nested quote inside the first."""
    body = _decl("notes-list.js", "renderNoteText")
    assert "mdQuoteElement(quoted" in body and "renderNoteText(host" in body
    assert "leave it to the inline pass" not in body
    css = "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "frontend" / "css").glob("*.css"))
    assert "#entry-list blockquote" in css
