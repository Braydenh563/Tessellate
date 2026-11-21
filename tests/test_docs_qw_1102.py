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
from tests._app_js import documents_text

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
DOCS = documents_text()

node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not available")


def _slice(source: str, head: str, tail: str) -> str:
    start = source.index(head)
    return source[start : source.index(tail, start) + len(tail)]


def _node(script: str, *sources: str) -> dict:
    done = subprocess.run(
        ["node", "-e", ("const vm=require('node:vm');const ctx={};vm.createContext(ctx);"
                        "for (const s of JSON.parse(process.argv[1])) vm.runInContext(s, ctx);"
                        "console.log(JSON.stringify(vm.runInContext(process.argv[2], ctx)));"),
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


# DX32 ----------------------------------------------------------------------


@node
def test_dx32_a_word_list_paragraph_is_a_list_item_with_or_without_its_style():
    fn = _slice(DOCS, "function docWordListLine(el, styleOf, inline) {", "\n}\n")
    out = _node(
        """(() => {
          const el = (text, { cls = "", styles = {} } = {}) => ({
            textContent: text, childNodes: [{ nodeValue: text }], styles,
            getAttribute: (name) => (name === "class" ? cls : ""),
            querySelectorAll: () => [],
          });
          const styleOf = (e, prop) => e.styles[prop] || "";
          const inline = (node) => node.nodeValue;
          const line = (e) => docWordListLine(e, styleOf, inline);
          return {
            glyph: line(el("\\u00b7 first item")),
            bullet: line(el("\\u2022\\u00a0\\u00a0two")),
            cls: line(el("alpha", { cls: "MsoListParagraphCxSpFirst" })),
            styled: line(el("kept", { styles: { "mso-list": "l0 level2 lfo1" } })),
            indent: line(el("nested", { cls: "MsoListParagraph", styles: { "margin-left": "1.0in" } })),
            o: line(el("o  nested bullet")),
            plainO: line(el("o major point")),
            plain: line(el("Just a paragraph")),
            empty: line(el("\\u00b7 ")),
          };
        })()""",
        fn,
    )
    assert out["glyph"] == "- first item"
    assert out["bullet"] == "- two"
    assert out["cls"] == "- alpha"
    assert out["styled"] == "  - kept"
    assert out["indent"] == "  - nested"
    assert out["o"] == "- nested bullet"
    assert out["plainO"] == "" and out["plain"] == "" and out["empty"] == ""


def test_dx32_a_list_at_the_start_of_a_paste_is_kept():
    # Before (p/dx32.js, 8791): a Word list that opened the paste was appended to `out[-1]` (both
    # sides of the comparison were -1), so the converter returned "" and "· kept" arrived as text.
    assert "if (wordRun >= 0 && wordRun === out.length - 1)" in DOCS
    assert "|MsoList|mso-list/i;" in DOCS


# DX27 ----------------------------------------------------------------------


def test_dx27_a_version_preview_is_words_not_markup():
    # The history list and the Library card share this one stripper (`/revisions` and
    # `_summary`). Before: `==highlight==`, `[ ] task`, `:-:, --:, ---` and `[!note] A note`
    # reached the row. The lines are still lines here; once joined they could not be told apart.
    from tessellate.api.routes_documents import _preview

    text = (
        "# T\n\n==highlight== text\n\n- [ ] task one\n- [x] done two\n\n"
        "| a | b | c |\n|:-:|--:|---|\n| 1 | 2 | 3 |\n\n---\n\n> [!note] A note\n> body\n\n1. first\n"
    )
    assert _preview(text) == "T · highlight text · task one · done two · a, b, c · 1, 2, 3 · A note · body · first"
    assert _preview("***\nreal words") == "real words"
    assert _preview("[brackets] stay and [ ] in the middle stay") == "[brackets] stay and [ ] in the middle stay"


# DX14, DX15 ----------------------------------------------------------------


def _list_helpers() -> str:
    return (
        _slice(PROSE, "function docListEnter(line) {", "\n}\n")
        + _slice(PROSE, "docListEnter.backspace = ", ";\n")
        + _slice(PROSE, "docListEnter.renumber = ", "\n};\n")
    )


@node
def test_dx14_backspace_on_an_empty_list_item_removes_the_marker_and_its_indent():
    out = _node(
        """({
          bullet: docListEnter.backspace("- "),
          nested: docListEnter.backspace("    - "),
          numbered: docListEnter.backspace("12. "),
          task: docListEnter.backspace("- [ ] "),
          text: docListEnter.backspace("- one"),
          quote: docListEnter.backspace("> "),
          plain: docListEnter.backspace("hello"),
        })""",
        _list_helpers(),
    )
    assert out["bullet"] == out["nested"] == out["numbered"] == out["task"] == ""
    assert out["text"] is None and out["quote"] is None and out["plain"] is None


@node
def test_dx15_an_ordered_list_is_numbered_again_around_an_edit():
    out = _node(
        """(() => {
          const apply = (text, touched) => {
            const lines = text.split("\\n");
            for (const [i, from, to, insert] of docListEnter.renumber(lines, touched)) lines[i] = lines[i].slice(0, from) + insert + lines[i].slice(to);
            return lines.join("\\n");
          };
          return {
            gap: apply("1. a\\n3. c\\n4. d", [0, 1]),
            keepsStart: apply("3. a\\n5. c\\n6. d", [1]),
            lazy: apply("1. a\\n1. b\\n1. c", [1]),
            single: apply("4. only", [0]),
            nested: apply("1. a\\n   1. x\\n   3. y\\n3. b", [3]),
            nestedRun: apply("1. a\\n   1. x\\n   3. y\\n3. b", [2]),
            blank: apply("1. a\\n\\n3. b", [2]),
            twoBlanks: apply("1. a\\n\\n\\n3. b", [3]),
            other: apply("1. a\\n3) b", [0, 1]),
            fence: apply("1. a\\n```\\n1. x\\n3. y\\n```", [3]),
            bullets: apply("- a\\n- b", [0, 1]),
            text: apply("1. a\\nplain\\n3. b", [0]),
          };
        })()""",
        _list_helpers(),
    )
    assert out["gap"] == "1. a\n2. c\n3. d"
    assert out["keepsStart"] == "3. a\n4. c\n5. d"
    assert out["lazy"] == "1. a\n1. b\n1. c", "a list numbered 1 throughout is left alone"
    assert out["single"] == "4. only"
    assert out["nested"] == "1. a\n   1. x\n   3. y\n2. b", "the outer run counts past its nested list"
    assert out["nestedRun"] == "1. a\n   1. x\n   2. y\n3. b"
    assert out["blank"] == "1. a\n\n2. b", "a loose list is one list"
    assert out["twoBlanks"] == "1. a\n\n\n3. b", "two blank lines end it"
    assert out["other"] == "1. a\n3) b", "another delimiter is another list"
    assert out["fence"] == "1. a\n```\n1. x\n3. y\n```", "code is not a list"
    assert out["bullets"] == "- a\n- b"
    assert out["text"] == "1. a\nplain\n3. b", "a paragraph ends the list"


def test_dx14_dx15_are_wired_into_the_editor():
    assert "docListEnter.backspace(line.text) === \"\"" in PROSE
    assert "CM.state.EditorState.transactionFilter.of((tr) => {\n    if (!tr.docChanged || tr.newDoc.lines === tr.startState.doc.lines) return tr;" in PROSE
    assert "sequential: true" in PROSE
    assert "docProseGhostPlugin(CM), docProsePairKeymap(CM), docListFenceExtensions(CM, true), renumber]" in PROSE


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
