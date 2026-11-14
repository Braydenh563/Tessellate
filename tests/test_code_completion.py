"""Code documents as a code editor, part three: completions, Emmet, ghost text.

The owner, 2026-09-23 (INBOX 394 (c)): "on the document editor code files I
want ALL THE PREFILL SUGGESTIONS AND POPUP BOXES FOR OPTIONS. like if I do
just '!' on a document and press enter it does base html code, or for all
the available css properties for that css feature, or doinf inline
suggestions."

The list itself is CodeMirror's own and is measured in Chromium by
`scratchpad/ui-sweeps/doccomplete.js`. What decides *which words are offered
and what text results* is pure string work in documents.js's `DOC-COMPLETE`
region, run here in node against the vendored Emmet bundle itself, so an
expansion is held to the exact text it must produce.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
#: documents.js and the two files split out of it on 2026-09-24, joined:
#: the code side (documents-code.js) and the prose tools (documents-prose.js)
#: moved there verbatim, and the wiring that mounts them stayed in
#: documents.js, so a test that reads "the documents editor" reads all three.
DOCUMENTS_JS = tuple(
    ROOT / "frontend" / "js" / name
    for name in ("documents.js", "documents-code-format.js", "documents-code.js", "documents-prose.js", "documents-cm.js", "documents-cm-theme.js")
)


def _documents_text() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in DOCUMENTS_JS)
EMMET_JS = ROOT / "frontend" / "vendor" / "emmet" / "emmet.min.js"

node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def _source() -> str:
    return _documents_text()


def _region() -> str:
    text = _source()
    start, stop = text.find("// DOC-COMPLETE-BEGIN"), text.find("// DOC-COMPLETE-END")
    assert start != -1 and stop > start, "the DOC-COMPLETE markers are missing from documents-code.js"
    return text[start:stop]


def _function(name: str) -> str:
    """The function's text; a lazy piece indents it and a stand-in of the same name sits in another file, so the longest wins."""
    text = _source()
    found = []
    for m in re.finditer(rf"^( *)(?:async )?function {name}\(", text, re.M):
        end = text.index("\n" + m.group(1) + "}\n", m.start())
        found.append(text[m.start() : end])
    return max(found, key=len)


def run(calls: list) -> list:
    """Evaluate `[name, *args]` calls against the region, with `E` the bundle."""
    script = (
        EMMET_JS.read_text(encoding="utf-8")
        + "\n"
        + _region()
        + "\nconst E = EMMET;\n"
        "const fns = {docEmmetAt, docGhostSuffix, docCssValueContext};\n"
        "fns.at = (line, col, syntax, anywhere) => {"
        " const f = docEmmetAt(line, col, syntax, E, anywhere); return f && [f.abbr, f.start, f.end]; };\n"
        "fns.expand = (abbr, syntax) => { const x = docEmmetExpansion(E, abbr, syntax);"
        " return x && [x.preview, x.template]; };\n"
        "fns.values = (property) => docCssValueOptions(property, docCssValueTable(E)).map((o) => o.label);\n"
        "const calls = JSON.parse(process.argv[1]);\n"
        "console.log(JSON.stringify(calls.map(([name, ...args]) => fns[name](...args))));\n"
    )
    out = subprocess.run(
        ["node", "-e", script, json.dumps(calls)], capture_output=True, text=True, check=True, timeout=60
    )
    return json.loads(out.stdout)


def one(name: str, *args):
    return run([[name, *args]])[0]


# --- Emmet: which text is an abbreviation ------------------------------------


@node
@pytest.mark.parametrize(
    ("line", "col", "syntax", "anywhere", "found"),
    [
        # The owner's case: `!` alone on a line.
        ("!", 1, "html", False, ["!", 0, 1]),
        ("  !", 3, "html", False, ["!", 2, 3]),
        ("div.card>ul>li*3", 16, "html", False, ["div.card>ul>li*3", 0, 16]),
        # The closer `closeBrackets` typed ahead of the caret is part of it.
        ("a[href]", 6, "html", False, ["a[href]", 0, 7]),
        ("p{text}", 6, "html", False, ["p{text}", 0, 7]),
        # Straight after a tag on the same line.
        ("<div>ul>li", 10, "html", False, ["ul>li", 5, 10]),
        # A tag's name on its own line is offered; a word of prose is not.
        ("  section", 9, "html", False, ["section", 2, 9]),
        ("  hello", 7, "html", False, None),
        # Mid-sentence, never on typing (a paragraph would pop a list at
        # every "a" and "p"), but Tab asks for it on purpose.
        ("Read this p", 11, "html", False, None),
        ("Read this p", 11, "html", True, ["p", 10, 11]),
        # A caret inside a word is not at the end of an abbreviation.
        ("divider", 3, "html", False, None),
        # CSS: Emmet's own shorthands at a property's place.
        ("  m10", 5, "css", False, ["m10", 2, 5]),
        ("  df", 4, "css", False, ["df", 2, 4]),
        ("a { bgc", 7, "css", False, ["bgc", 4, 7]),
        ("  jcc", 5, "css", False, ["jcc", 2, 5]),
        # A property name being typed is the language's list, not Emmet's,
        # and so is what Emmet could only make `columns: ;` of.
        ("  col", 5, "css", False, None),
        ("  pos", 5, "css", False, None),
        ("  color", 7, "css", False, None),
        # One letter is every property that starts with it: noise.
        ("  c", 3, "css", False, None),
        # In a value, never.
        ("  color: re", 11, "css", False, None),
    ],
)
def test_the_abbreviation_at_the_caret(line, col, syntax, anywhere, found):
    assert one("at", line, col, syntax, anywhere) == found


@node
def test_bang_expands_to_the_html5_boilerplate():
    preview, template = one("expand", "!", "html")
    assert preview.startswith("<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n")
    assert "\t<meta charset=\"UTF-8\">\n" in preview
    assert "<title>Document</title>" in preview
    assert preview.endswith("<body>\n\t\n</body>\n</html>")
    #: Tab stops: the title is a field with its placeholder, the body a bare
    #: one, in CodeMirror's own snippet syntax.
    assert "<title>${5:Document}</title>" in template
    assert "<body>\n\t${6}\n</body>" in template
    #: The viewport's defaults are text: the first stop is the title.
    assert 'content="width=device-width, initial-scale=1.0"' in template
    assert re.findall(r"\$\{(\d+)", template) == ["5", "6"]
    #: An empty attribute keeps its stop.
    assert one("expand", "a[href]", "html")[1] == '<a href="${1}">${2}</a>'


@node
@pytest.mark.parametrize(
    ("abbr", "preview"),
    [
        ("div.card>ul>li*3", "<div class=\"card\">\n\t<ul>\n\t\t<li></li>\n\t\t<li></li>\n\t\t<li></li>\n\t</ul>\n</div>"),
        ("a[href]", "<a href=\"\"></a>"),
        ("p{text}", "<p>text</p>"),
        ("ul>li.item$*2", "<ul>\n\t<li class=\"item1\"></li>\n\t<li class=\"item2\"></li>\n</ul>"),
    ],
)
def test_markup_expansions(abbr, preview):
    got, template = one("expand", abbr, "html")
    assert got == preview
    #: The template is the preview with its tab stops marked and nothing else.
    assert re.sub(r"\$\{\d+(?::([^{}]*))?\}", lambda m: m.group(1) or "", template) == preview


@node
def test_braces_in_the_text_are_escaped_for_the_snippet_parser():
    """CodeMirror reads `${...}` and `#{...}` as fields; a brace that is text
    must reach it escaped or the expansion is cut at it."""
    preview, template = one("expand", "p{a {b} c}", "html")
    assert preview == "<p>a {b} c</p>"
    assert template == "<p>a \\{b\\} c</p>"


@node
@pytest.mark.parametrize(
    ("abbr", "preview"),
    [("m10", "margin: 10px;"), ("df", "display: flex;"), ("bgc", "background-color: #fff;"), ("p10-20", "padding: 10px 20px;")],
)
def test_stylesheet_expansions(abbr, preview):
    assert one("expand", abbr, "css")[0] == preview


# --- CSS: each property's own values -----------------------------------------


@node
@pytest.mark.parametrize(
    ("before", "found"),
    [
        ("a {\n  color: ", {"property": "color", "word": ""}),
        ("a { display: fl", {"property": "display", "word": "fl"}),
        ("a { border: 1px sol", {"property": "border", "word": "sol"}),
        ("a { color: red; marg", None),
        ("a { color: red;", None),
        ("a {", None),
    ],
)
def test_the_value_context(before, found):
    assert one("docCssValueContext", before) == found


@node
def test_each_property_offers_its_own_values():
    display, color, position, width, writing, cursor = run(
        [["values", p] for p in ("display", "color", "position", "width", "writing-mode", "cursor")]
    )
    #: Emmet's table is its abbreviations, not a reference: what it lacks is
    #: added and what is dead is dropped.
    assert "fit-content" in width and "auto" in width
    assert "vertical-rl" in writing and "lr-tb" not in writing
    assert "not-allowed" in cursor and "hand" not in cursor
    for word in ("flex", "grid", "none", "block", "inline-block", "contents"):
        assert word in display
    #: Its own values first, then the four every property takes.
    assert display.index("flex") < display.index("inherit")
    for word in ("red", "rebeccapurple", "transparent", "currentcolor", "inherit"):
        assert word in color
    for word in ("absolute", "relative", "fixed", "static", "sticky"):
        assert word in position
    #: A property with no keyword list still gets the four, not nothing.
    assert {"inherit", "initial", "unset", "revert"} <= set(width)
    assert len(display) == len(set(display)), "a value is offered twice"


# --- the ghost text ------------------------------------------------------------


@node
@pytest.mark.parametrize(
    ("before", "after", "label", "ghost"),
    [
        ("  col", "", "color", "or"),
        ("  Col", "", "color", "or"),
        ("x = docu", ")", "document", "ment"),
        # Only the rest of a word the caret ends; never inside one.
        ("  col", "x", "color", ""),
        # The typed text must be the start of a word, not the tail of one.
        ("  xcol", "", "color", ""),
        # A fuzzy match has no rest to show.
        ("  bgc", "", "background-color", ""),
        ("  color", "", "color", ""),
        ("  !", "", "!", ""),
        ("  de", "", "def\nx", ""),
    ],
)
def test_the_ghost_suffix(before, after, label, ghost):
    assert one("docGhostSuffix", before, after, label) == ghost


# --- wiring, which the sweep measures in Chromium ------------------------------


def test_emmet_is_vendored_with_its_licence_and_loaded_on_demand():
    vendor = ROOT / "frontend" / "vendor" / "emmet"
    for name in ("emmet.min.js", "LICENSE", "build.sh", "package.json", "entry.js"):
        assert (vendor / name).is_file(), f"frontend/vendor/emmet/{name} is missing"
    licence = (vendor / "LICENSE").read_text(encoding="utf-8")
    assert licence.startswith("MIT License") and "emmet 2.4.11" in licence
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert "/vendor/emmet" not in html, "Emmet is for HTML and CSS documents, loaded when one opens"
    assert 'DOC_EMMET_BUNDLE = "/vendor/emmet/emmet.min.js"' in _source()


def test_the_tools_stay_off_for_prose_and_plain():
    tools = _function("docCodeTools")
    assert "type.previewable" in tools and 'docView === "plain"' in tools
    #: Plain text keeps its inert completer: no sources, no typing trigger.
    #: Markdown has one source since doclist-1108, the `#tag` list, which
    #: answers only while a `#word` is typed (the stated intent moved there).
    #: And a second since live code blocks (2026-11-10): the fence source,
    #: which answers only inside a fenced block that names a language.
    #: And a third, the reference source (live math blocks): the list is
    #: tag, reference, fence for markdown and empty for everything else.
    assert 'override: type.ext === "md" ? [docPairInput.tagSource(CM), docPairInput.refSource(CM), docPairInput.fenceSource(CM)] : []' in tools
    assert 'activateOnTyping: type.ext === "md"' in tools
    assert "docCompletionExtras(CM, type)" in tools


def test_tab_accepts_the_suggestion_and_enter_stays_the_lists():
    extras = _function("docCompletionExtras")
    assert 'key: "Tab"' in extras and "Prec.highest" in extras
    tab = _function("docCompleteTab")
    assert "acceptCompletion(view)" in tab and "docEmmetExpandAtCaret(view" in tab
    assert "Enter" not in extras, "Enter belongs to the list's own keymap"


def test_css_uses_its_own_source_in_place_of_the_packages():
    """`override` so the value list is the property's own and not the
    package's flat list with it added on top (every value twice)."""
    extras = _function("docCompletionExtras")
    assert 'if (type.ext === "css") config.override = docCssSources(CM);' in extras
    source = _function("docCssCompletionSource")
    assert "CM.css.cssCompletionSource(context)" in source


def test_the_ghost_and_the_preview_are_drawn_in_the_apps_ink():
    theme = _source().split("function docCmTheme(CM) {", 1)[1].split("\nfunction ", 1)[0]
    ghost = theme.split('".cm-ghostText"', 1)[1].split("}", 1)[0]
    assert 'color: "var(--muted)"' in ghost
    info = theme.split('".cm-tooltip.cm-completionInfo"', 1)[1].split("}", 1)[0]
    assert "var(--modal-bg-opaque)" in info


# --- INBOX 402: Emmet beyond HTML, wrap and balance ------------------------------


def run402(calls: list) -> list:
    script = (
        EMMET_JS.read_text(encoding="utf-8")
        + "\n"
        + _region()
        + "\nconst E = EMMET;\n"
        "const fns = {};\n"
        "fns.at = (line, col, syntax, anywhere) => {"
        " const f = docEmmetAt(line, col, syntax, E, anywhere); return f && f.abbr; };\n"
        "fns.expand = (abbr, syntax, text) => { const x = docEmmetExpansion(E, abbr, syntax, text);"
        " return x && x.preview; };\n"
        "fns.wrap = (abbr, syntax, text, indent) => { const x = docEmmetExpansion(E, abbr, syntax,"
        " docEmmetWrapText(text, indent, abbr)); return x && x.preview; };\n"
        "fns.balance = (src, from, to, inward) => { const o = { xml: true };"
        " const into = inward && from !== to;"
        " const tags = into ? E.balancedInward(src, from, o) : E.balancedOutward(src, from, o);"
        " return docBalanceRange(tags, from, to, into); };\n"
        "const calls = JSON.parse(process.argv[1]);\n"
        "console.log(JSON.stringify(calls.map(([name, ...args]) => fns[name](...args))));\n"
    )
    out = subprocess.run(
        ["node", "-e", script, json.dumps(calls)], capture_output=True, text=True, check=True, timeout=60
    )
    return json.loads(out.stdout)


@node
@pytest.mark.parametrize(
    ("line", "col", "syntax", "anywhere", "found"),
    [
        # JSX: an element, a component, an operator; never the page.
        ("    div.card", 12, "jsx", False, "div.card"),
        ("    Card>Item", 13, "jsx", False, "Card>Item"),
        ("    !", 5, "jsx", False, None),
        # XML: any name, but on typing only with an operator.
        ("  item>name", 11, "xml", False, "item>name"),
        ("  row*3", 7, "xml", False, "row*3"),
        ("  item", 6, "xml", False, None),
        ("  item", 6, "xml", True, "item"),
    ],
)
def test_emmet_in_jsx_and_xml(line, col, syntax, anywhere, found):
    assert run402([["at", line, col, syntax, anywhere]])[0] == found


@node
def test_jsx_writes_classname_and_xml_closes_empty_elements():
    jsx, xml, br = run402([["expand", "div.card>p", "jsx"], ["expand", "item[id=1]>name{x}", "xml"], ["expand", "br", "xml"]])
    assert jsx == '<div className="card">\n\t<p></p>\n</div>'
    assert xml == '<item id="1">\n\t<name>x</name>\n</item>'
    assert br == "<br/>"


@node
def test_wrap_with_an_abbreviation():
    one_block, per_line, indented = run402(
        [
            ["wrap", "div.box", "html", "<p>x</p>", ""],
            ["wrap", "ul>li*", "html", "one\ntwo", ""],
            #: The lines after the first lose the first line's indent, which
            #: the snippet puts back, so a wrapped block does not drift right.
            ["wrap", "section", "html", "<p>a</p>\n    <p>b</p>", "    "],
        ]
    )
    assert one_block == '<div class="box">\n\t<p>x</p>\n</div>'
    assert per_line == "<ul>\n\t<li>one</li>\n\t<li>two</li>\n</ul>"
    assert indented == "<section>\n\t<p>a</p>\n\t<p>b</p>\n</section>"


_SRC = "<div>\n  <p>hi <b>there</b></p>\n</div>"


@node
def test_balance_steps_out_and_back_in():
    #: From a caret in "hi": the p's content, the p, the div's content, the div.
    out1, out2, out3, out4, edge = run402(
        [
            ["balance", _SRC, 12, 12, False],
            ["balance", _SRC, 11, 26, False],
            ["balance", _SRC, 8, 30, False],
            ["balance", _SRC, 5, 31, False],
            ["balance", _SRC, 0, 37, False],
        ]
    )
    assert out1 == [11, 26] and out2 == [8, 30] and out3 == [5, 31] and out4 == [0, 37]
    assert edge is None
    in1, in2 = run402([["balance", _SRC, 0, 37, True], ["balance", _SRC, 5, 31, True]])
    assert in1 == [5, 31] and in2 == [8, 30]


def test_emmet_commands_are_in_the_palette_for_code():
    source = _source()
    table = source[source.index("// DOC-COMMANDS-BEGIN") : source.index("// DOC-COMMANDS-END")]
    for command in ("docEmmetWrap()", "docEmmetBalance(false)", "docEmmetBalance(true)"):
        assert command in table
    assert "code: true, run: () => docEmmetWrap()" in table
    extras = _function("docCompletionExtras")
    assert 'CM.javascript.javascriptLanguage.data.of({ autocomplete: docEmmetSource(CM, "jsx") })' in extras
    assert "docJsxChildAt(CM, state, pos)" in _function("docEmmetPlace")


def _region_call(expr: str, arg) -> object:
    """`expr` evaluated after the region and the bundle, `ARG` its argument."""
    script = (
        EMMET_JS.read_text(encoding="utf-8")
        + "\n"
        + _region()
        + "\nconst E = EMMET;\nconst ARG = JSON.parse(process.argv[1]);\n"
        + f"console.log(JSON.stringify({expr}));\n"
    )
    out = subprocess.run(["node", "-e", script, json.dumps(arg)], capture_output=True, text=True, check=True, timeout=60)
    return json.loads(out.stdout)


@node
@pytest.mark.parametrize(
    ("text", "edit", "partner"),
    [
        # Typing in the open tag's name renames the close, shifted by the edit.
        ("<div>\n  x\n</div>", [1, 4, "section"], {"from": 16, "to": 19, "insert": "section"}),
        ("<div>x</div>", [4, 4, "s"], {"from": 9, "to": 12, "insert": "divs"}),
        # And in the close tag's name, the open, which does not move.
        ("<div>x</div>", [8, 11, "p"], {"from": 1, "to": 4, "insert": "p"}),
        # Deleting a letter.
        ("<span>x</span>", [4, 5, ""], {"from": 8, "to": 12, "insert": "spa"}),
        # A space starts the attributes: the partner is left alone.
        ("<div>x</div>", [4, 4, " "], None),
        # Not in a name, or no partner.
        ("<div>x</div>", [5, 6, "y"], None),
        ("<br>", [1, 3, "hr"], None),
        # XML names with a prefix.
        ("<a:b>x</a:b>", [3, 4, "c"], {"from": 8, "to": 11, "insert": "a:c"}),
    ],
)
def test_rename_the_matching_tag(text, edit, partner):
    got = _region_call("docTagRename(E, ARG[0], ARG[1], ARG[2], ARG[3], true)", [text, *edit])
    assert got == partner


@node
@pytest.mark.parametrize(
    ("fn", "before", "name"),
    [
        ("docXmlOpenedBy", "<root>\n  <item", "item"),
        ("docXmlOpenedBy", '<item id="1"', "item"),
        ("docXmlOpenedBy", "<br/", None),
        ("docXmlOpenedBy", "<!-- x", None),
        ("docXmlOpenedBy", "<?xml version", None),
        ("docXmlOpenedBy", "</item", None),
        ("docXmlUnclosed", "<root>\n  <item>x", "item"),
        ("docXmlUnclosed", "<root>\n  <item>x</item>\n", "root"),
        ("docXmlUnclosed", "<root><br/><!-- <x> -->", "root"),
        ("docXmlUnclosed", "<root></root>", None),
    ],
)
def test_xml_auto_close(fn, before, name):
    assert _region_call(f"{fn}(ARG)", before) == name


def test_tag_link_is_one_undo_step_and_mounted_where_there_are_tags():
    link = _function("docTagLink")
    assert "transactionFilter" in link and "sequential: true" in link
    assert 'tr.isUserEvent("input.type") || tr.isUserEvent("delete")' in link
    extras = _function("docCompletionExtras")
    assert '["html", "xml", "js"].includes(type.ext) ? docTagLink(CM, DOC_EMMET_SYNTAX[type.ext]) : []' in extras
    assert 'type.ext === "xml" ? docXmlAutoClose(CM) : []' in extras


@node
@pytest.mark.parametrize(
    ("original", "hex_", "written"),
    [
        ("#f00", "#00ff00", "#00ff00"),
        ("#F00", "#00ff00", "#00FF00"),
        # The alpha is kept, whichever length it came in.
        ("#f008", "#00ff00", "#00ff0088"),
        ("#ff000080", "#0000ff", "#0000ff80"),
        # Functions keep their syntax and their alpha.
        ("rgb(255, 0, 0)", "#010203", "rgb(1, 2, 3)"),
        ("rgba(255, 0, 0, 0.5)", "#010203", "rgba(1, 2, 3, 0.5)"),
        ("rgb(255 0 0 / 50%)", "#010203", "rgb(1 2 3 / 50%)"),
        # The picker has only hex to give for the rest.
        ("hsl(0, 100%, 50%)", "#010203", "#010203"),
        ("red", "#010203", "#010203"),
    ],
)
def test_a_picked_colour_is_written_in_the_values_own_form(original, hex_, written):
    assert _region_call("docCssColorFormat(ARG[0], ARG[1])", [original, hex_]) == written


@node
@pytest.mark.parametrize(
    ("computed", "hex_"),
    [("rgb(255, 0, 0)", "#ff0000"), ("rgba(1, 2, 3, 0.5)", "#010203"), ("rgb(0 128 0)", "#008000"), ("transparent", None)],
)
def test_the_computed_colour_as_the_pickers_hex(computed, hex_):
    assert _region_call("docRgbToHex(ARG)", computed) == hex_


def test_swatches_are_drawn_from_the_tree_for_css_and_html():
    swatches = _function("docColorSwatches")
    for name in ('"CallExpression"', '"ValueName"', '"ColorLiteral"', "view.visibleRanges", 'CSS.supports("color"'):
        assert name in swatches
    assert '["css", "html"].includes(type.ext) ? docColorSwatches(CM) : []' in _function("docCompletionExtras")
    picker = _function("docColorAt")
    assert 'input.type = "color"' in picker and "input.showPicker()" in picker
    assert ".setAttribute(\"style\"" not in picker, "the CSP refuses a style attribute"
    theme = _source().split("function docCmTheme(CM) {", 1)[1].split("\nfunction ", 1)[0]
    swatch = theme.split('".cm-color-swatch"', 1)[1].split("}", 1)[0]
    assert "var(--border)" in swatch and "var(--radius-inner)" in swatch


@node
def test_hover_lines():
    got = _region_call(
        "[docHoverLine('html', 'nav'), docHoverLine('attr', 'href'), "
        "docHoverLine('css', 'display', docCssValueTable(E)), docHoverLine('css', 'grid-area', docCssValueTable(E)), "
        "docHoverLine('html', 'blink'), "
        "[...DOC_HTML_TAGS].filter((t) => !docHoverLine('html', t))]",
        None,
    )
    nav, href, display, grid_area, unknown, missing = got
    assert nav == "A block of navigation links."
    assert href == "The address a link points to."
    first, values = display.split("\n")
    assert first.startswith("How the box is laid out")
    assert values.startswith("Values: ") and "flex" in values and values.endswith(", and more.")
    #: A property with no keyword list: its line alone.
    assert grid_area == "The grid area an item is placed in."
    assert unknown is None
    #: Every element the Emmet check knows has its line.
    assert missing == []


def test_hover_docs_are_our_own_words_and_on_the_hover_card():
    source = _source()
    region = source[source.index("const DOC_HOVER_HTML = `") : source.index("function docHoverLine(")]
    assert chr(0x2014) not in region and "MDN" in source[source.index("One line on what a name is for") - 200 : source.index("const DOC_HOVER_HTML = `")]
    hover = _function("docHoverDocs")
    assert "CM.view.hoverTooltip" in hover
    assert '{ PropertyName: "css", TagName: "html", AttributeName: "attr" }' in hover
    #: Python joined for its standard library signatures (OPEN 1070).
    assert '["css", "html", "py"].includes(type.ext) ? docHoverDocs(CM) : []' in _function("docCompletionExtras")
    theme = source.split("function docCmTheme(CM) {", 1)[1].split("\nfunction ", 1)[0]
    assert '".cm-hover-doc-values": { color: "var(--muted)"' in theme


# --- js-beautify behind Format (docs42b) ------------------------------------

BEAUTIFY_JS = ROOT / "frontend" / "vendor" / "js-beautify" / "beautify.min.js"


def test_js_beautify_is_vendored_with_its_licence_and_loaded_on_demand():
    """Brief 42 kept js-beautify (a third of prettier) for Format on js,
    css and html. Like Emmet: never at boot, fetched the first time Format
    runs on one of the three, and a selection keeps the conservative path."""
    vendor = BEAUTIFY_JS.parent
    for name in ("beautify.min.js", "LICENSE", "build.sh", "package.json", "entry.js"):
        assert (vendor / name).is_file(), f"frontend/vendor/js-beautify/{name} is missing"
    assert (vendor / "LICENSE").read_text(encoding="utf-8").startswith("The MIT License")
    assert '"js-beautify": "2.0.3"' in (vendor / "package.json").read_text(encoding="utf-8")
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    app = (ROOT / "frontend" / "js" / "app.js").read_text(encoding="utf-8")
    assert "js-beautify" not in html and "js-beautify" not in app
    assert 'DOC_BEAUTIFY_BUNDLE = "/vendor/js-beautify/beautify.min.js"' in _source()
    fmt = _function("docFormatCode")
    assert "DOC_BEAUTIFY_TYPES.has(type.ext) && (await docLoadBeautify())" in fmt
    assert "else if (selection && beautify) {" in fmt and "indent_level: level" in _function("docBeautifyText")
    assert "else if (beautify) result = docBeautifyText(text, type.ext, unit);" in fmt


@node
def test_js_beautify_formats_in_the_documents_own_indent_unit():
    script = (
        "const fs = require('fs'); const vm = require('vm');"
        f"vm.runInThisContext(fs.readFileSync({json.dumps(str(BEAUTIFY_JS))}, 'utf8') + ';globalThis.JSBEAUTIFY = JSBEAUTIFY;');"
        f"vm.runInThisContext({json.dumps(_function('docBeautifyText') + chr(10) + '}')});"
        "process.stdout.write(JSON.stringify(["
        "docBeautifyText('function f(a){if(a){return <div>x</div>}}', 'js', '  ').text,"
        "docBeautifyText('a{color:red}', 'css', '\\t').text,"
        "docBeautifyText('<ul><li>a</li></ul>', 'html', '    ').text,"
        "docBeautifyText('  ', 'js', '  ').changed]));"
    )
    out = json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True, timeout=60).stdout)
    assert out[0] == "function f(a) {\n  if (a) {\n    return <div>x</div>\n  }\n}\n"
    assert out[1] == "a {\n\tcolor: red\n}\n"
    assert out[2] == "<ul>\n    <li>a</li>\n</ul>\n"
    assert out[3] is False


@node
def test_js_beautify_formats_a_selection_at_its_own_indent_level_with_no_trailing_newline():
    """Ledger 1565: a selection of whole lines keeps the level of its first line."""
    script = (
        "const fs = require('fs'); const vm = require('vm');"
        f"vm.runInThisContext(fs.readFileSync({json.dumps(str(BEAUTIFY_JS))}, 'utf8') + ';globalThis.JSBEAUTIFY = JSBEAUTIFY;');"
        f"vm.runInThisContext({json.dumps(_function('docBeautifyText') + chr(10) + '}')});"
        "process.stdout.write(JSON.stringify(docBeautifyText('if(a){b()}', 'js', '  ', {level: 2, endWithNewline: false}).text));"
    )
    out = json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True, timeout=60).stdout)
    assert out == "    if (a) {\n      b()\n    }"
