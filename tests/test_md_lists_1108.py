"""The renderer reads the list markers the editor keeps (INBOX 1696 cc, laglist-1108).

The editor's List and Numbered menus write the style into the marker (`docLists`,
documents-cm.js): `-` dots, `*` circles, `+` squares, a dash is `-` with two spaces,
`1.` and `1)` numbers, `a.` letters and `i.` roman numerals. The renderer and the
exports (the HTML export is built from the rendered DOM) used to read only `-`, `*`,
`+` and `1.`, so `1)`, `a.` and `i.` came out as plain paragraphs and a change of
marker did not start a new list.

The pure half (`mdList`, between the MD-LISTS markers in markdown.js) runs here in node;
the DOM half is the loop in navigation.js, driven in a browser (laglist-1108.md has the
numbers: getComputedStyle of each list and of its marker, in the app and in the export).
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MARKDOWN_JS = ROOT / "frontend" / "js" / "markdown.js"
NAVIGATION_JS = ROOT / "frontend" / "js" / "navigation.js"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")

DRIVER = r"""
const out = {};
const item = (line, cur = null) => { const r = mdList.item(line, cur); return r && { key: r.key, text: r.text, fresh: !!r.fresh }; };
out.dash = item("- one");
out.star = item("* one");
out.plus = item("+ one");
out.twoSpaces = item("-  one");
out.twoSpacesTask = item("-  [ ] one");
out.oneSpaceTask = item("- [x] one");
out.decimal = item("3. three");
out.paren = item("3) three");
out.alphaStart = item("a. first");
out.alphaNext = item("b. second", { key: "ol-a-dot", count: 1, indent: "" });
out.alphaGap = item("c. third", { key: "ol-a-dot", count: 1, indent: "" });
out.alphaNotA = item("b. alone");
out.romanStart = item("i. first");
out.romanNext = item("ii. second", { key: "ol-i-dot", count: 1, indent: "" });
out.romanFour = item("iv. fourth", { key: "ol-i-dot", count: 3, indent: "" });
out.romanSixty = item("lx. sixtieth", { key: "ol-i-dot", count: 59, indent: "" });
out.romanLong = item("lxxxviii. eighty-eighth", { key: "ol-i-dot", count: 87, indent: "" });
out.iAfterH = item("i. ninth letter", { key: "ol-a-dot", count: 8, indent: "" });
out.notRoman = item("iiii. nope", { key: "ol-i-dot", count: 3, indent: "" });
out.sentence = item("A. Smith wrote it");
out.word = item("and. no");
out.nestedLetter = item("  a. nested", { key: "ol-1-dot", count: 1, indent: "" });
out.inParagraph = item("a. in a paragraph", false);
out.plain = item("Just a line");
out.noSpace = item("-not a list");
out.indent = mdList.item("    * deeper").indent;
process.stdout.write(JSON.stringify(out));
"""


@pytest.fixture(scope="module")
def r() -> dict:
    text = MARKDOWN_JS.read_text(encoding="utf-8")
    begin, end = "// MD-LISTS-BEGIN", "// MD-LISTS-END"
    start, stop = text.find(begin), text.find(end)
    assert start != -1 and stop > start, "MD-LISTS markers missing from markdown.js"
    script = text[start + len(begin) : stop] + DRIVER
    done = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def test_the_three_bullet_markers_and_the_dash_are_four_styles(r):
    assert r["dash"]["key"] == "ul-disc"
    assert r["star"]["key"] == "ul-circle"
    assert r["plus"]["key"] == "ul-square"
    assert r["twoSpaces"]["key"] == "ul-dash"
    #: A task keeps its dots, as in the editor (`parse`).
    assert r["twoSpacesTask"]["key"] == "ul-disc" and r["oneSpaceTask"]["key"] == "ul-disc"
    assert r["dash"]["text"] == "one"


def test_numbers_with_a_dot_or_a_bracket_are_two_lists(r):
    assert r["decimal"]["key"] == "ol-1-dot" and r["decimal"]["text"] == "three"
    assert r["paren"]["key"] == "ol-1-paren"


def test_letters_and_roman_numerals_are_a_list_only_as_a_run(r):
    assert r["alphaStart"]["key"] == "ol-a-dot"
    assert r["alphaNext"]["key"] == "ol-a-dot" and not r["alphaNext"]["fresh"]
    assert r["romanStart"]["key"] == "ol-i-dot"
    assert r["romanNext"]["key"] == "ol-i-dot" and not r["romanNext"]["fresh"]
    assert r["romanFour"]["key"] == "ol-i-dot" and not r["romanFour"]["fresh"]
    #: `i.` after `h.` is the ninth letter, not a numeral.
    assert r["iAfterH"]["key"] == "ol-a-dot" and not r["iAfterH"]["fresh"]
    #: A letter that is neither the start nor the next one is text.
    assert r["alphaGap"] is None and r["alphaNotA"] is None
    # L307: the numeral keeps counting past 59 (it stopped at "l" before).
    assert r["romanSixty"]["key"] == "ol-i-dot" and not r["romanSixty"]["fresh"]
    assert r["romanLong"]["key"] == "ol-i-dot" and not r["romanLong"]["fresh"]
    assert r["notRoman"] is None and r["sentence"] is None and r["word"] is None
    #: A letter item under a deeper indent than the list is not a new list.
    assert r["nestedLetter"] is None
    #: Inside a paragraph only a bullet or a number opens a list.
    assert r["inParagraph"] is None


def test_what_is_not_a_marker_stays_text(r):
    assert r["plain"] is None and r["noSpace"] is None
    assert r["indent"] == "    "


def test_the_renderer_reads_every_line_through_the_one_parser():
    nav = NAVIGATION_JS.read_text(encoding="utf-8")
    assert "const entry = at(line);" in nav and "mdList.item(l, list" in nav
    #: The old pair of regexes is gone: one parser, not two beside each other.
    assert "line.match(/^\\s*[-*+]\\s+(.*)$/)" not in nav
    assert "/^\\s*\\d+\\.\\s+(.*)$/" not in nav
    #: The paragraph stops at the same lines that open a list.
    assert "!mdList.item(lines[i], false)" in nav
    #: The list's class is its key, which the stylesheet and the export's own turn into the marker.
    assert "list.className = `md-${entry.key}`" in nav


def test_every_key_has_a_marker_rule_in_the_app_and_the_export():
    css = (ROOT / "frontend" / "css" / "01-forms-settings.css").read_text(encoding="utf-8")
    export = (ROOT / "frontend" / "js" / "documents-export.js").read_text(encoding="utf-8")
    for cls in ("md-ul-circle", "md-ul-square", "md-ul-dash", "md-ol-a-dot", "md-ol-i-dot", "md-ol-1-paren"):
        assert f".{cls}" in css, cls
        assert f".{cls}" in export, cls
