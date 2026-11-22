"""INBOX 1545: `:ph-check:` is the icon in a document's Live view, Read view
and export; an unknown name stays text.

The owner inserted an icon from the picker and saw the token, not the glyph.
Notes drew it (`highlightIconsInto`); a document's Read view, Live view and
HTML export did not, because their prose goes through `appendPlainText`, which
only knew the checkbox token. The class: every reader of the token asks one
function, `appendPlainText.icon` (documents.js), which answers from the font's
own stylesheet, so a name the font lacks is never drawn as an empty box.

The browser checks (Live, Read, export, measured) are in the commit message;
this runs the hook and `appendPlainText` in node with a fake DOM.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
NOTES = (JS / "notes-list.js").read_text(encoding="utf-8")
DOCS = (JS / "documents.js").read_text(encoding="utf-8")
CM = (JS / "documents-cm.js").read_text(encoding="utf-8")
EXPORT = (JS / "documents-export.js").read_text(encoding="utf-8")

node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not available")


def _function(source: str, head: str) -> str:
    start = source.index(head)
    return source[start : source.index("\n}\n", start) + 3]


def _hook() -> str:
    start = DOCS.index("appendPlainText.icon = (name) => {")
    return DOCS[start : DOCS.index("\n};\n", start) + 4]


HARNESS = r"""
const vm = require("node:vm");
const src = process.argv[1];
const rules = ["check", "star"].map((n) => ({ selectorText: `.ph.ph-${n}::before` }));
class El {
  constructor(tag) { this.tag = tag; this.kids = []; }
  append(...n) { this.kids.push(...n.map((x) => (typeof x === "string" ? { text: x } : x))); }
}
const ctx = {
  Object, Array, document: {
    createElement: (t) => new El(t),
    styleSheets: process.argv[2] === "nosheet" ? [] : [{ href: "http://x/vendor/phosphor/style.css", cssRules: rules }],
  },
};
vm.createContext(ctx);
vm.runInContext(src, ctx);
const out = (e) => e.kids.map((k) => (k.text !== undefined ? k.text : k.tag === "i" ? `<${k.className}|${k.ariaLabel}>` : `[${k.type}:${k.checked}]`)).join("");
const run = (text) => { const e = new El("p"); ctx.appendPlainText(e, text); return out(e); };
console.log(JSON.stringify({
  known: run("a :ph-check: b"),
  unknown: run("a :ph-notanicon-zz: b"),
  mixed: run("[x] :ph-star: [ ] :ph-nope:"),
  plain: run("no tokens"),
}));
"""


def _run(*extra: str) -> dict:
    prose = _function(NOTES, "function appendPlainText(element, text) {")
    done = subprocess.run(
        ["node", "-e", HARNESS, prose + "\n" + _hook(), *extra],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(done.stdout)


@node
def test_a_known_icon_is_drawn_and_an_unknown_name_stays_text():
    out = _run()
    assert out["known"] == "a <ph ph-check md-inline-icon|check> b"
    assert out["unknown"] == "a :ph-notanicon-zz: b"
    assert out["plain"] == "no tokens"


@node
def test_the_checkbox_token_still_works_beside_an_icon():
    assert _run()["mixed"] == "[checkbox:true] <ph ph-star md-inline-icon|star> [checkbox:false] :ph-nope:"


@node
def test_without_the_hook_a_token_is_text_not_an_empty_box():
    # notes-list.js alone (chat, search snippets, any reader outside documents)
    prose = _function(NOTES, "function appendPlainText(element, text) {")
    done = subprocess.run(
        ["node", "-e", HARNESS, prose, "nosheet"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(done.stdout)["known"] == "a :ph-check: b"


def test_the_hook_asks_the_font_and_lets_every_name_through_when_it_cannot():
    hook = _hook()
    assert "phosphor" in hook and "cssRules" in hook
    assert "selectorText === `.ph.ph-${name}::before`" in hook
    # an unreadable or missing sheet is "known": the old behaviour, not a regression
    assert "catch {\n      known[name] = true;" in hook
    assert "!sheet ||" in hook


def test_live_view_replaces_the_token_with_the_same_icon_unless_the_caret_is_in_it():
    assert "class DocIconWidget extends WidgetType" in CM
    scan = CM[CM.index("scan(/:ph-([a-z0-9-]{1,40}):/g") :]
    scan = scan[: scan.index("});") + 3]
    assert "appendPlainText.icon(match[1])" in scan
    # The caret rule is the widget one since INBOX 1547 (source while a selection starts in it).
    assert "widgetRevealed(from, to)" in scan
    assert "Decoration.replace({ widget: new DocIconWidget(match[1]) })" in scan
    # `scan` skips code, so a token in a code span or block stays text
    assert "const scan = " in CM or "function scan(" in CM


def test_export_embeds_the_glyphs_and_the_font_only_when_an_icon_is_present():
    body = EXPORT[EXPORT.index("docExportHtmlDocument.icons = async") :]
    assert "i.md-inline-icon" in body
    assert 'getComputedStyle(icon, "::before").content' in body
    assert "/vendor/phosphor/Phosphor-full.woff2" in body
    # no icon, no font: the early return comes before the fetch
    assert body.index("return \"\"") < body.index("fetch(")
    assert "${DOC_EXPORT_CSS}${extraCss}" in EXPORT
    assert "await docExportHtmlDocument.icons($(\"doc-preview\"), clone)" in EXPORT
    # the clone is rewritten before the export clean strips `i.ph`
    run = EXPORT[EXPORT.index("await docExportHtmlDocument.icons(") :]
    assert "docExportClean(clone)" in run[: run.index("docExportHtmlDocument(")]
