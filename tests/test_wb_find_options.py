"""Find options, placeholders and tooltips (whiteboard-1018 step 7;
WHITEBOARD_PLAN sections 3 and 9). Find and replace share one pure pattern
builder with a whole-word and a regular-expression option; find also reads an
item's data values; a label's `%name%` shows the item's own value of that
name; `data.tip` is the shape's hover text. The browser half is run outside
the repo (the sweep named in HISTORY)."""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WB = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")
FMT = (ROOT / "frontend" / "js" / "whiteboard-format.js").read_text(encoding="utf-8")
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")


def _function(name: str, src: str = WB) -> str:
    start = src.index(f"function {name}(")
    return src[start : src.index("\n}\n", start) + 3]


def _node(expr: str):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    code = "".join(_function(n) for n in ("wbSearchPattern", "wbReplaceText", "wbExpandPlaceholders")) + f"console.log(JSON.stringify({expr}));"
    return json.loads(subprocess.run([node, "-e", code], capture_output=True, text=True, check=True).stdout)


def _has(query, text, **opts):
    return _node(f"(() => {{ const p = wbSearchPattern({json.dumps(query)}, {json.dumps(opts)}); return p.re ? p.has({json.dumps(text)}) : null; }})()")


def test_literal_find_ignores_case_and_escapes():
    assert _has("a.b", "xa.by") is True
    assert _has("a.b", "axb") is False
    assert _has("SHIP", "ship it") is True


def test_whole_word_stops_at_word_characters():
    assert _has("cat", "concatenate", word=True) is False
    assert _has("cat", "the cat sat", word=True) is True
    assert _has("cat", "cat.", word=True) is True
    #: A word edge is not `\b`: "c++" ends on a symbol and must still be found.
    assert _has("c++", "i like c++ a lot", word=True) is True
    assert _has("c++", "c+++", word=True) is True


def test_regex_option_and_bad_patterns():
    assert _has(r"ship\s+\d+", "ship  12", regex=True) is True
    assert _has(r"^ship$", "first\nship\nlast", regex=True) is True
    assert _node('wbSearchPattern("(", {regex: true}).error') == "Not a valid pattern"
    assert _node('wbSearchPattern("(", {regex: true}).re') is None
    #: A pattern that matches nothing would match everywhere.
    assert _node('wbSearchPattern("a*", {regex: true}).error') == "This pattern matches empty text"
    assert _node('wbSearchPattern("   ").error') == ""
    assert _node('wbSearchPattern("").re') is None
    #: The same text in literal mode is only characters.
    assert _has("(", "a (b)") is True


def test_replace_with_options():
    assert _node('wbReplaceText("Ship it, SHIP again, shipping", "ship", "send", {word: true})') == {"text": "send it, send again, shipping", "count": 2}
    assert _node('wbReplaceText("v12 and v7", "v(\\\\d+)", "build $1", {regex: true})') == {"text": "build 12 and build 7", "count": 2}
    assert _node('wbReplaceText("a-b", "(a)-(b)", "$2-$1-$$-$&", {regex: true})') == {"text": "b-a-$-a-b", "count": 1}
    #: Literal replace keeps `$` literal, as before.
    assert _node('wbReplaceText("x", "x", "$1$&")') == {"text": "$1$&", "count": 1}
    assert _node('wbReplaceText("nothing", "(", "y", {regex: true})') == {"text": "nothing", "count": 0}


def test_placeholders_read_the_items_own_values():
    assert _node('wbExpandPlaceholders("Owner: %owner% (%team%)", {owner: "Sam", team: "Ops"})') == "Owner: Sam (Ops)"
    #: An unknown name stays as typed, so a stray percent sign is not eaten.
    assert _node('wbExpandPlaceholders("100% of %none%", {owner: "Sam"})') == "100% of %none%"
    assert _node('wbExpandPlaceholders("%toString% %__proto__%", {})') == "%toString% %__proto__%"
    assert _node('wbExpandPlaceholders("%a%", null)') == "%a%"
    assert _node('wbExpandPlaceholders("no marks", {a: "b"})') == "no marks"


def test_find_and_replace_share_the_builder():
    run = _function("wbBoardSearchRun")
    assert "wbSearchPattern(" in run and ".toLowerCase()" not in run
    replace = WB[WB.index("async function wbBoardReplaceAll(") :]
    replace = replace[: replace.index("\n}\n")]
    assert "wbSearchPattern(" in replace and "wbReplaceText(field, needle, to, wbBoardSearch)" in replace
    #: Find reads the item's data values (its own `props`).
    text = _function("wbSearchTextFor")
    assert text.count("props") >= 2


def test_option_buttons_are_built_lazily_and_named():
    assert 'id="wb-search-word"' not in HTML and 'id="wb-search-regex"' not in HTML
    build = _function("wbEnsureSearchOptions")
    for needle in ('"wb-search-word"', '"wb-search-regex"', "aria-pressed", "Whole word", "Pattern"):
        assert needle in build
    assert "wbEnsureSearchOptions(bar)" in _function("wbOpenBoardSearch")


def test_date_and_page_are_built_ins_that_own_properties_beat():
    """`%date%` and `%page%` come from the builtin; a property of the same name wins; no answer keeps the text."""
    b = "(n) => ({date: '18 Oct 2026', page: 'Intro'})[n]"
    assert _node(f'wbExpandPlaceholders("%date% on %page%", null, {b})') == "18 Oct 2026 on Intro"
    assert _node(f'wbExpandPlaceholders("%page%", {{page: "Mine"}}, {b})') == "Mine"
    assert _node('wbExpandPlaceholders("%page%", {}, () => "")') == "%page%"
    assert _node(f'wbExpandPlaceholders("%owner%", {{}}, {b})') == "%owner%"


def test_labels_paint_placeholders_and_a_tooltip():
    shape = _function("wbPaintShapeLabel")
    assert "wbExpandPlaceholders(parsed.label, parsed.props, " in shape and "wbPlaceholderBuiltins" in shape
    link = _function("wbPaintLinkLabel")
    assert "wbExpandPlaceholders(parsed.label, parsed.props, " in link and "wbPlaceholderBuiltins" in link
    tip = _function("wbSyncSketchTip")
    assert "title" in tip and "createElementNS" in tip and "parsed?.tip" in tip
    #: Run once per sketch with the shape's or the connector's data. Run from
    #: each painter it would strip the other kind's tip on every render.
    assert len(re.findall(r"wbSyncSketchTip\(", WB)) == 2
    assert "wbSyncSketchTip(this, look)" in WB


def test_tooltip_row_and_handler():
    assert 'data-fmt="tip"' in HTML and 'id="wb-fmt-tip"' in HTML
    for kind in ("shape", "line", "arrow", "link"):
        row = re.search(rf"^  {kind}: \[(.*)\],$", FMT, re.M).group(1)
        assert '"tip"' in row, kind
    assert 'case "tip"' in FMT and 'on("wb-fmt-tip"' in FMT


def test_help_names_the_options():
    ai = ROOT / "src" / "tessellate" / "ai"
    help_text = (ai / "help_chat.py").read_text(encoding="utf-8") + (ai / "help_topics_more.py").read_text(encoding="utf-8")
    for needle in ("whole word", "pattern", "%name%", "tooltip"):
        assert needle in help_text.lower()
