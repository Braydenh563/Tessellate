"""Documents audit 1102 quick wins (DX3, DX4, DX7, DX10, DX11, DX14, DX15, DX27, DX32).

Each class is fixed once, in the one function every caller asks. The pure
functions run in node here; the browser numbers (before and after) are in the
commit messages.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
DOCS = (JS / "documents.js").read_text(encoding="utf-8")

node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not available")


def _slice(source: str, head: str, tail: str) -> str:
    start = source.index(head)
    return source[start : source.index(tail, start) + len(tail)]


def _node(script: str, *sources: str) -> dict:
    done = subprocess.run(
        ["node", "-e", "const vm=require('node:vm');const ctx={};vm.createContext(ctx);"
         "for (const s of JSON.parse(process.argv[1])) vm.runInContext(s, ctx);"
         "console.log(JSON.stringify(vm.runInContext(process.argv[2], ctx)));",
         json.dumps(list(sources)), script],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(done.stdout)


# DX3 -----------------------------------------------------------------------


@node
def test_dx3_a_pasted_block_starts_its_own_line():
    fit = _slice(DOCS, "docRichPasteEvent.fit = ", "\n};\n")
    out = _node(
        """({
          heading: docRichPasteEvent.fit("## Two\\n\\n- a", "Pick here please", ""),
          fence: docRichPasteEvent.fit("```\\ncode\\n```", "Pick ", ""),
          quote: docRichPasteEvent.fit("> quoted", "x", ""),
          table: docRichPasteEvent.fit("| a |\\n| - |", "x", ""),
          paras: docRichPasteEvent.fit("one\\n\\ntwo", "x", ""),
          before_and_after: docRichPasteEvent.fit("- a", "x", " tail"),
          at_line_start: docRichPasteEvent.fit("## Two", "", ""),
          indent_only: docRichPasteEvent.fit("## Two", "   ", ""),
          inline: docRichPasteEvent.fit("**bold**", "x", "y"),
          link: docRichPasteEvent.fit("[a](http://x)", "x", ""),
        })""",
        "function docRichPasteEvent() {}\n" + fit,
    )
    assert out["heading"] == "\n\n## Two\n\n- a"
    assert out["fence"].startswith("\n\n```")
    assert out["quote"] == "\n\n> quoted"
    assert out["table"].startswith("\n\n| a |")
    assert out["paras"] == "\n\none\n\ntwo"
    assert out["before_and_after"] == "\n\n- a\n\n"
    assert out["at_line_start"] == "## Two"
    assert out["indent_only"] == "## Two"
    assert out["inline"] == "**bold**"
    assert out["link"] == "[a](http://x)"


def test_dx3_the_paste_writes_the_fitted_text_and_offers_it():
    body = _slice(DOCS, "function docRichPasteEvent(event, view) {", "\n}\n")
    assert "docRichPasteEvent.fit(markdown," in body
    assert "insert: markdown" not in body
    assert "docPasteOfferRich(view, sel.from, insert," in body


# DX4 -----------------------------------------------------------------------


def test_dx4_the_tab_hatch_is_disarmed_before_any_keymap_can_swallow_the_key():
    # Before (p/dx4.js, 8791): Escape, ArrowLeft, Tab left the editor for the status bar and
    # indented nothing, because the arrow was handled by the keymap before the disarming
    # handler (default precedence) was asked. The handler is now Prec.highest.
    start = DOCS.index("//: The disarming half of the Escape-then-Tab hatch.")
    body = DOCS[start : DOCS.index("//: Ahead of the markdown language's own paste-a-URL", start)]
    assert "CM.state.Prec.highest(CM.view.EditorView.domEventHandlers({" in body
    assert 'event.key !== "Tab" && event.key !== "Shift" && event.key !== "Escape"' in body
    assert "mousedown: () => {\n        docTabEscapes = false;" in body
    assert "docTableCellClick(event, view)" in body


def test_dx4_an_escape_that_closes_a_menu_does_not_arm_the_hatch():
    start = DOCS.index('      key: "Escape",')
    body = DOCS[start : DOCS.index('key: "Tab",', start)]
    assert "docTabEscapes = ![...document.querySelectorAll('[role=\"menu\"], .cm-tooltip')]" in body


# DX7 -----------------------------------------------------------------------

EDITOR = (JS / "editor.js").read_text(encoding="utf-8")


@node
def test_dx7_a_slash_command_runs_on_past_a_space_while_a_row_holds_the_words():
    token = _slice(EDITOR, "function editorTokenAt(textarea, trigger) {", "\n}\n")
    phrase = _slice(EDITOR, "editorTokenAt.phrase = ", "\n};\n")
    stubs = (
        "const rows=[{label:'Page break',keywords:['new page']},{label:'Heading 4',keywords:['h4']},"
        "{label:'Link to a note',keywords:['wiki']}];"
        "function editorCommands(){return rows;} function editorSurfaceKind(){return 'document';}"
    )
    out = _node(
        """(() => {
          const at = (text) => { const t = { value: text, selectionStart: text.length }; return editorTokenAt(t, "/"); };
          return {
            pageBreak: at("/page break"),
            heading4: at("/heading 4"),
            link: at("/link to a note"),
            trailing: at("/heading "),
            keyword: at("/new page"),
            prose: at("/page and then"),
            slashSpace: at("/ x"),
            unknown: at("/zzz more"),
            tooLong: at("/link to a note and more"),
            word: at("/page"),
          };
        })()""",
        stubs + token + phrase,
    )
    assert out["pageBreak"]["fragment"] == "page break"
    assert out["heading4"]["fragment"] == "heading 4"
    assert out["link"]["fragment"] == "link to a note"
    assert out["trailing"]["fragment"] == "heading "
    assert out["keyword"]["fragment"] == "new page"
    assert out["word"]["fragment"] == "page"
    for closed in ("prose", "slashSpace", "unknown", "tooLong"):
        assert out[closed] is None, closed


def test_dx7_heading_rows_four_to_six_are_in_the_menu():
    for n in (4, 5, 6):
        assert f'id: "h{n}", group: "Basic"' in EDITOR
        assert f'run: act("h{n}")' in EDITOR


# DX10 ----------------------------------------------------------------------

WIRING = (JS / "settings-wiring.js").read_text(encoding="utf-8")
PROSE = (JS / "documents-prose.js").read_text(encoding="utf-8")


@node
def test_dx10_one_word_count_for_the_bar_the_goal_the_selection_and_the_statistics():
    counts = WIRING[WIRING.index("const TEXT_READING_WPM") : WIRING.index("function captureCountText")]
    plain = _slice(PROSE, "function docPlainText(text) {", "\n}\n")
    prop = _slice(PROSE, "docPlainText.counts = ", ";\n")
    stats = PROSE[PROSE.index("const DOC_STOP_WORDS") : PROSE.index("function docOpenStatistics")]
    table = "| a | b |\n|---|---|\n| one | two |\n\n- first item\n- second item\n\n---\n\nThree plain words."
    out = _node(
        f"""(() => {{
          const text = {json.dumps(table)};
          const bar = docPlainText.counts(text);
          const stats = docStatistics(text);
          return {{ bar: bar.words, stats: stats.words, barMinutes: bar.minutes, statsMinutes: stats.readMinutes, raw: textCounts(text).words }};
        }})()""",
        counts + stats,
    )
    assert out["bar"] == out["stats"] == 11, out
    assert out["raw"] > out["bar"], "the raw markdown counts pipes and rules as words"
    assert out["barMinutes"] == out["statsMinutes"], "one reading speed"
    assert plain and prop


def test_dx10_every_reader_asks_the_one_function():
    bar = _slice(DOCS, "function renderDocCounts() {", "\n}\n")
    assert "docPlainText.counts(stripped)" in bar and "textCounts(stripped)" in bar
    goal = _slice(DOCS, "function renderDocStats() {", "\n}\n")
    assert "docPlainText.counts(docCommentStrip(docText()))" in goal
    assert "docPlainText.counts(docCommentStrip(box.text.slice(range.from, range.to)))" in DOCS
    assert "readMinutes: total.minutes" in PROSE and "/ 238" not in PROSE


# DX11 ----------------------------------------------------------------------

UNDO = (JS / "undo-store.js").read_text(encoding="utf-8")
LIBRARY = (JS / "library.js").read_text(encoding="utf-8")


@node
def test_dx11_a_purged_document_takes_its_history_its_kept_edit_and_its_position():
    out = _node(
        """(() => {
          const deleted = [];
          undoStoreRequest = (mode, act) => { act({ delete: (name) => { deleted.push(name); return {}; } }); return Promise.resolve(null); };
          const store = { "doc-edit-drafts": { 7: { id: 7 }, 8: { id: 8 } }, "doc-positions": { 7: { top: 1 }, 9: { top: 2 } } };
          globalThis.prefs = { json: (k, f) => store[k] ?? f, setJSON: (k, v) => { store[k] = v; } };
          undoStoreClear.purged("document", 7);
          undoStoreClear.purged("note", 12);
          return { deleted, store };
        })()""",
        "var clearTimeout = () => {}; var undoStoreTimers = new Map();"
        + _slice(UNDO, "function undoStoreRequest(", "\n}\n")
        + _slice(UNDO, "function undoStoreClear() {", "\n}\n")
        + _slice(UNDO, "undoStoreClear.one = ", "\n};\n")
        + _slice(UNDO, "undoStoreClear.purged = ", "\n};\n"),
    )
    assert out["deleted"] == ["doc:7", "board:12"]
    assert out["store"]["doc-edit-drafts"] == {"8": {"id": 8}}
    assert out["store"]["doc-positions"] == {"9": {"top": 2}}


def test_dx11_every_purge_path_forgets_what_this_device_kept():
    # One item (the Library menu), the bulk delete, the bin's reader and emptying the bin.
    assert LIBRARY.count("undoStoreClear.purged(") == 4
    assert "for (const item of binned) undoStoreClear.purged(binRoutes(item).noun, item.id);" in LIBRARY
