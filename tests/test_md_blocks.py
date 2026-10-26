"""The block vocabulary the "/" menu writes parses the way it is documented.

INBOX 421 b: the owner asked for the "/" blocks to be "an actual proper thing
the user's can use to properly structure out their documents and notes".
Markdown stays the storage format, so every block is a spelling in the text,
and the spellings are parsed by small pure functions that the renderers
(`renderMarkdown`, `renderNoteText`) and the Live view all call. Two marked
regions hold them, both runnable in node with no DOM:

* `MD-BLOCKS-BEGIN` / `MD-BLOCKS-END` in app.js: columns, dividers, quote
  attribution, the table of contents and the callout head.
* `EDITOR-BLOCKS-BEGIN` / `EDITOR-BLOCKS-END` in editor.js: the callout
  kinds with their aliases, and the "/" menu's fuzzy ranking.

What matters most is what must *not* become a block: a `:::columns` inside a
code fence, an unclosed columns block, a dash line inside a quote that is not
the last line, a `$5 and $10` that is prices rather than maths.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from tests._app_js import app_js_text

ROOT = Path(__file__).resolve().parents[1]
APP_JS = ROOT / "frontend" / "js" / "app.js"
EDITOR_JS = ROOT / "frontend" / "js" / "editor.js"


def region(path: Path, name: str) -> str:
    #: app.js means the app's code, every piece of it (tests/_app_js.py).
    text = app_js_text() if path == APP_JS else path.read_text(encoding="utf-8")
    begin, end = f"// {name}-BEGIN", f"// {name}-END"
    start, stop = text.find(begin), text.find(end)
    assert start != -1, f"{begin} is missing from {path.name}"
    assert stop > start, f"{end} is missing or before {begin} in {path.name}"
    return text[start + len(begin) : stop]


DRIVER = r"""
const out = {};
const lines = (s) => s.split("\n");

// --- columns ---------------------------------------------------------------
out.cols2 = mdColumnsFrom(lines(":::columns\nLeft\n:::column\nRight\n:::\nafter"), 0);
out.cols3 = mdColumnsFrom(lines(":::columns 3\nA\n:::column\nB\n:::column\nC\n:::"), 0);
out.colsUnclosed = mdColumnsFrom(lines(":::columns\nLeft\n:::column\nRight"), 0);
out.colsFenced = mdColumnsFrom(lines(":::columns\n```\n:::\n```\n:::column\nR\n:::"), 0);
out.colsNotOpen = mdColumnsFrom(lines("text\n:::columns"), 0);

// --- dividers ---------------------------------------------------------------
out.dividers = ["---", "***", "* * *", "___", "- - -", "--", "text", "-----"].map(mdDividerKind);

// --- quote attribution ------------------------------------------------------
out.cite = mdQuoteAttribution(["Stay hungry.", "-- Steve Jobs"]);
out.citeDash = mdQuoteAttribution(["Words.", "\u2014 Someone"]);
out.citeOnly = mdQuoteAttribution(["-- just a dash line"]);
out.citeMiddle = mdQuoteAttribution(["One", "-- not last", "Two"]);

// --- table of contents -------------------------------------------------------
out.tocLine = ["[TOC]", "[toc]", "  [TOC]  ", "[TOC] extra", "[[toc]]"].map((l) => MD_TOC_LINE.test(l));
out.toc = mdTocEntries("# Title\n\n[TOC]\n\n## One\ntext\n```\n## not a heading\n```\n### Two *b*\n#nothashtag");

// --- display maths -----------------------------------------------------------
out.mathBlock = mdMathBlockFrom(lines("$$\n\\frac{a}{b}\n$$\nafter"), 0);
out.mathOneLine = mdMathBlockFrom(lines("$$ x^2 $$"), 0);
out.mathUnclosed = mdMathBlockFrom(lines("$$\nx"), 0);
out.mathPrices = mdMathBlockFrom(lines("$5 and $10"), 0);

// --- callout head -------------------------------------------------------------
out.callout = [
  "[!note] Title here", "[!WARNING]- Folded", "[!tip]+", "[!caution] Alias",
  "[!tldr] Short", "[!unknownkind] Odd", "not a callout", "[!toggle]- Details",
].map((l) => mdCalloutHead(l));

// --- the editor's kinds and ranking ------------------------------------------
out.kinds = Object.keys(CALLOUT_KINDS);
out.kindOf = ["note", "Warning", "caution", "hint", "done", "error", "cite", "tldr", "nope", ""].map(calloutKindOf);
out.everyKindHasIconAndLabel = Object.values(CALLOUT_KINDS).every((k) => /^ph:[a-z-]+$/.test(k.icon) && k.label && k.about);
const rows = [
  { id: "h2", label: "Heading 2", keywords: ["h2", "section"] },
  { id: "toc", label: "Table of contents", keywords: ["toc", "outline"] },
  { id: "tbl", label: "Table", keywords: ["grid"] },
  { id: "warn", label: "Warning callout", keywords: ["caution", "box"] },
  { id: "cols", label: "Two columns", keywords: ["layout", "side by side"] },
];
out.rank = {
  table: editorFuzzyRank(rows, "table").map((r) => r.id),
  ta: editorFuzzyRank(rows, "ta").map((r) => r.id),
  toc: editorFuzzyRank(rows, "toc").map((r) => r.id),
  twcl: editorFuzzyRank(rows, "twcl").map((r) => r.id),
  box: editorFuzzyRank(rows, "box").map((r) => r.id),
  zz: editorFuzzyRank(rows, "zz").map((r) => r.id),
  empty: editorFuzzyRank(rows, "").map((r) => r.id),
};
out.hits = editorFuzzyMatch("Table of contents", "tbc");
out.rewrite = [
  calloutRewriteHead("> [!warning]- Watch **this**", "tip", "+"),
  calloutRewriteHead("> [!note] T", "danger", ""),
  calloutRewriteHead("> plain quote", "tip", "-"),
];
out.hint = ["note", "todo", "warning", "nope"].map(calloutHint);
console.log(JSON.stringify(out));
"""


@pytest.fixture(scope="module")
def result() -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    source = region(APP_JS, "MD-BLOCKS") + "\n" + region(EDITOR_JS, "EDITOR-BLOCKS") + "\n" + DRIVER
    proc = subprocess.run([node, "-e", source], capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def test_two_and_three_columns(result):
    assert [c.strip() for c in result["cols2"]["columns"]] == ["Left", "Right"]
    assert result["cols2"]["end"] == 5, "the index after the closing `:::`"
    assert [c.strip() for c in result["cols3"]["columns"]] == ["A", "B", "C"]


def test_columns_that_are_not_blocks(result):
    assert result["colsUnclosed"] is None, "somebody halfway through typing one"
    assert result["colsNotOpen"] is None
    fenced = result["colsFenced"]
    assert fenced is not None, "a ``` fence inside a column is content, not the close"
    assert [c.strip() for c in fenced["columns"]] == ["```\n:::\n```", "R"]


def test_divider_kinds(result):
    assert result["dividers"] == ["line", "dots", "dots", "thick", "line", None, None, "line"]


def test_quote_attribution(result):
    assert result["cite"] == {"body": ["Stay hungry."], "cite": "Steve Jobs"}
    assert result["citeDash"] == {"body": ["Words."], "cite": "Someone"}
    assert result["citeOnly"]["cite"] is None, "a quote that is only a dash line is a quote"
    assert result["citeMiddle"]["cite"] is None, "only the last line attributes"


def test_table_of_contents(result):
    assert result["tocLine"] == [True, True, True, False, False]
    assert result["toc"] == [
        {"level": 1, "text": "Title"},
        {"level": 2, "text": "One"},
        {"level": 3, "text": "Two *b*"},
    ], "headings inside a code fence and a #hashtag are not entries"


def test_display_maths(result):
    assert result["mathBlock"] == {"tex": "\\frac{a}{b}", "end": 3}
    assert result["mathOneLine"] == {"tex": "x^2", "end": 1}
    assert result["mathUnclosed"] is None
    assert result["mathPrices"] is None


def test_callout_head(result):
    note, warning, tip, caution, tldr, unknown, plain, toggle = result["callout"]
    assert note == {"kind": "note", "raw": "note", "fold": "", "title": "Title here"}
    assert warning == {"kind": "warning", "raw": "WARNING", "fold": "-", "title": "Folded"}
    assert tip["fold"] == "+" and tip["title"] == ""
    assert caution["kind"] == "warning", "Obsidian's aliases land on their kind"
    assert tldr["kind"] == "abstract"
    assert unknown["kind"] == "note", "an unknown kind still renders as a box"
    assert plain is None
    assert toggle["kind"] == "toggle" and toggle["fold"] == "-"


def test_callout_kinds_cover_obsidian(result):
    for kind in ("note", "abstract", "info", "todo", "tip", "success", "question",
                 "warning", "failure", "danger", "bug", "example", "quote", "toggle"):
        assert kind in result["kinds"], kind
    assert result["everyKindHasIconAndLabel"], "each kind carries a ph: icon, a label and a line"
    assert result["kindOf"] == [
        "note", "warning", "warning", "tip", "success", "danger", "quote", "abstract", None, None,
    ]


def test_fuzzy_rank(result):
    rank = result["rank"]
    assert rank["ta"][:2] == ["toc", "tbl"], "a prefix of both keeps the menu order"
    assert rank["table"][:2] == ["tbl", "toc"], "a label that is the query ranks above a longer one that starts with it"
    assert rank["toc"][0] == "toc", "a keyword prefix finds the table of contents"
    assert rank["twcl"] == ["cols"], "letters in order anywhere in the label still match"
    assert rank["box"] == ["warn"]
    assert rank["zz"] == []
    assert rank["empty"] == ["h2", "toc", "tbl", "warn", "cols"], "no query keeps the order"
    assert result["hits"] == [0, 2, 9], "the matched letters, for the highlight"


def test_callout_rewrite_touches_only_the_marker(result):
    assert result["rewrite"] == [
        "> [!tip]+ Watch **this**",
        "> [!danger] T",
        "> plain quote",
    ]


def test_an_empty_callout_body_says_what_goes_there(result):
    """INBOX 486: the "/" menu wrote "What matters about this?" into the body
    as real text; the body is empty now and the Live view hints instead."""
    assert result["hint"] == ["Write the note", "Write the task", "Write the warning", "Write the note"]


def test_the_live_callout_shows_its_kind_once_and_no_markers():
    """INBOX 486, the owner: "I have no clue how to use these things". The
    Live view drew the kind as a word and the title beside it ("Note Note"),
    and showed `> [!note]` whenever the caret was on the line. The kind is its
    icon (a menu: a caret beside it), the word only stands in for a missing
    title, the markers never show, and an empty body gets a hint."""
    docs = (ROOT / "frontend" / "js" / "documents.js").read_text(encoding="utf-8")
    widget = docs[docs.index("class DocCalloutWidget") : docs.index("class DocCalloutHintWidget")]
    assert "if (!this.titled) chip.append(word)" in widget
    assert "cm-md-callout-caret" in widget
    quote = docs[docs.index('if (name === "Blockquote")') : docs.index('if (name === "FencedCode")')]
    assert "if (kind) {" in quote and "!rangeRevealed(first.from" not in quote
    assert "new DocCalloutHintWidget(calloutHint(kind))" in quote
    assert "!inCallout && touched(" in quote
    editor = EDITOR_JS.read_text(encoding="utf-8")
    assert "What matters about this?" not in editor
    assert "{ caretInside: true }" in editor
