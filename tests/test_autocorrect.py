"""Autocorrect outside the editor (Brief 94 (b), INBOX 850).

The owner: "is there an autocorrect feature with the ability to undo it??
everwhere on the app??" The document editor had one, behind its own menu.
`frontend/js/autocorrect.js` carries it to the note boxes, the chat and Ask
composers and the titles: one switch in Settings (on by default), never in
code, links, tags or search boxes, each correction underlined for five
seconds with a click that puts it back, Ctrl+Z or Backspace straight after
it undoing it, and the toast carrying Undo. The browser measurement is
`scratchpad/ui-sweeps/autocorrect94.js`; this file pins the rule.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend/js"
INDEX = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
SOURCE = (JS / "autocorrect.js").read_text(encoding="utf-8")

#: The boxes it serves: prose a person types. Capture, the edit form's two
#: fields (set in note-edit-panels.js), the graph's note boxes, Write with
#: the AI, quick note, the chat and Ask composers, and the titles.
SERVED = {
    "entry-content", "entry-title", "quick-note-text", "chat-input", "question",
    "graph-new-content", "graph-new-note-title", "graph-popup-content",
    "draft-text", "draft-thoughts", "doc-title",
}


def _tagged() -> dict[str, str]:
    out = {}
    for tag in re.findall(r"<(?:input|textarea)\b[^>]*>", INDEX):
        if "data-autocorrect" in tag:
            ident = re.search(r'\bid="([^"]+)"', tag)
            out[ident.group(1) if ident else tag] = tag
    return out


def test_the_prose_boxes_carry_it():
    assert set(_tagged()) == SERVED
    edit = (JS / "note-edit-panels.js").read_text(encoding="utf-8")
    assert edit.count("dataset.autocorrect") == 2


def test_never_in_code_links_tags_or_search():
    for ident, tag in _tagged().items():
        assert not re.search(r'type="(?:search|url|email|password|number)"', tag), ident
        assert 'spellcheck="false"' not in tag, ident
        assert not re.search(r"tag|url|search|css|code", ident), ident


def test_one_switch_in_settings_on_by_default(client):
    before = client.get("/preferences").json()
    put = client.put("/preferences", json={"autocorrect": False}).json()
    after = client.get("/preferences").json()
    assert before["autocorrect"] is True
    assert put["autocorrect"] is False and after["autocorrect"] is False
    general = INDEX[INDEX.index('id="settings-general"') : INDEX.index('id="settings-websearch"')]
    assert 'id="pref-autocorrect"' in general
    rows = (JS / "settings-rows.js").read_text(encoding="utf-8")
    assert '{ key: "autocorrect", id: "pref-autocorrect" }' in rows
    panes = (JS / "settings-panes.js").read_text(encoding="utf-8")
    assert 'autocorrect: $("pref-autocorrect").checked' in panes
    assert '"pref-autocorrect"' in panes
    assert "prefsCache?.autocorrect !== false" in SOURCE


def test_it_loads_on_the_first_focus_of_a_box_it_serves():
    wiring = (JS / "wiring.js").read_text(encoding="utf-8")
    assert 'lazyScript("/js/autocorrect.js")' in wiring
    docs = (JS / "documents.js").read_text(encoding="utf-8")
    #: The note boxes are CodeMirror once mounted; a typed change is handed
    #: over as an event rather than a call into a file that may not be in.
    assert '"note-typed"' in docs and '"note-typed"' in SOURCE


def test_undo_is_a_click_a_key_and_the_toast():
    assert "AUTOCORRECT_SECONDS = 5" in SOURCE
    assert '"Backspace"' in SOURCE and '=== "z"' in SOURCE
    assert 'toastAction(' in SOURCE and '"Undo"' in SOURCE
    assert "autocorrect-mark" in SOURCE
    css = "".join(p.read_text(encoding="utf-8") for p in (ROOT / "frontend/css").glob("*.css"))
    assert ".autocorrect-mark" in css


def _node(calls: list[str], dictionary: list[str] | None = None) -> list:
    node = shutil.which("node")
    if not node:  # pragma: no cover - node is in the sandbox and in CI
        pytest.skip("node is not available")
    script = f"""
const vm = require("vm");
const listeners = {{}};
const ctx = {{
  console, prefsCache: {{ writing_dictionary: {json.dumps(dictionary or [])} }},
  document: {{ addEventListener(name, fn) {{ listeners[name] = fn; }} }},
  window: {{ addEventListener() {{}} }},
}};
vm.createContext(ctx);
vm.runInContext(require("fs").readFileSync({json.dumps(str(JS / "autocorrect.js"))}, "utf8"), ctx);
const out = [];
for (const call of {json.dumps(calls)}) out.push(vm.runInContext(call, ctx) ?? null);
process.stdout.write(JSON.stringify(out));
"""
    done = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=60, check=False)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def _find(text: str, dictionary: list[str] | None = None):
    return _node([f"autocorrectFind({json.dumps(text)})"], dictionary)[0]


@pytest.mark.parametrize(
    ("text", "typed", "fixed"),
    [
        ("I ran teh ", "teh", "the"),
        ("Teh. ", "Teh", "The"),
        ("it shows everwhere,", "everwhere", "everywhere"),
        ("keep proffesionalising\n", "proffesionalising", "professionalising"),
        ("hwo ", "hwo", "how"),
        ("seperate ", "seperate", "separate"),
    ],
)
def test_a_finished_typo_is_corrected(text, typed, fixed):
    found = _find(text)
    assert found["typed"] == typed and found["fixed"] == fixed
    assert text[found["start"] : found["start"] + len(typed)] == typed


@pytest.mark.parametrize(
    "text",
    [
        "teh",  # not finished: on the way to "tehran"
        "see http://teh ",
        "#teh ",
        "`teh ",
        "```\nteh ",
        "path/teh ",
        "teh2 ",
        "these ",  # a real word
        "TEH ",  # an acronym or a shout, not prose
    ],
)
def test_never_in_code_links_tags_or_an_unfinished_word(text):
    assert _find(text) is None


def test_the_dictionary_and_a_word_put_back_are_never_rewritten():
    assert _find("teh ", ["teh"]) is None
    out = _node(['autocorrectRefused.add("teh")', 'autocorrectFind("teh ")'])
    assert out[1] is None


def test_the_table_holds_the_editors_and_the_owners_typos():
    docs = (JS / "documents.js").read_text(encoding="utf-8")
    body = docs[docs.index("const DOC_AUTOCORRECT = {") : docs.index("};", docs.index("const DOC_AUTOCORRECT = {"))]
    editor = set(re.findall(r"(\w+): \"", body))
    table = set(_node(["Object.keys(AUTOCORRECT_TYPOS)"])[0])
    assert editor <= table
    #: Brief 90's fixtures: the owner's own slips, the unambiguous ones.
    assert {"everwhere", "proffesionalising", "hwo", "cna", "mroe", "somthing", "featrues"} <= table
    #: A real word is never a key: the cost of being wrong is a silent change.
    assert not {"thes", "ny", "ro", "mut", "od", "cant", "dont", "ahs"} & table


def test_help_moves_with_it():
    from tessellate.ai import help_chat

    ids = [t["id"] for t in help_chat.topics_for("how do I turn off autocorrect")]
    assert ids and ids[0] == "autocorrect"
    topic = next(t for t in help_chat.HELP_TOPICS if t["id"] == "autocorrect")
    for words in ("Settings", "Backspace", "Ctrl+Z", "Undo", "never"):
        assert words in topic["body"], words
    dictionary_help = INDEX[INDEX.index('id="doc-dictionary-help"') :][:2000]
    assert "Settings, General" in dictionary_help


def test_a_click_on_the_underline_opens_a_menu_and_does_not_revert():
    # INBOX 904 B09: "when I clicked the word that was underlined, it instantly
    # reverted, it should show a little popup near the word for confirming or
    # reverting". The click opens `openMenuAtPoint`'s menu at the word (Keep,
    # Put back, Edit); only Put back reverts. Browser check:
    # scratchpad/ui-sweeps/autocorrectmenu.js.
    mark = SOURCE[SOURCE.index("function autocorrectMark(") :]
    mark = mark[: mark.index("\n}\n")]
    assert 'addEventListener("click", () => autocorrectMenu(entry))' in mark
    assert 'addEventListener("click", () => autocorrectUndo(entry))' not in mark
    menu = SOURCE[SOURCE.index("function autocorrectMenu(") :]
    menu = menu[: menu.index("\n}\n")]
    assert "openMenuAtPoint(" in menu
    for row in ("Keep", "Put back", "Edit"):
        assert row in menu, row
    assert "autocorrectUndo(entry)" in menu and "autocorrectForget(entry)" in menu


def test_hovering_the_underline_opens_the_same_menu():
    # INBOX 904 B04: "the user can hover over it and confirm it, edit it, or
    # rewind the change". A resting pointer opens the click's menu after a short
    # beat; leaving first cancels it; a finger (no hover) still clicks.
    mark = SOURCE[SOURCE.index("function autocorrectMark(") :]
    mark = mark[: mark.index("\n}\n")]
    assert '"pointerenter"' in mark and '"pointerleave"' in mark
    assert 'pointerType !== "mouse"' in mark
    assert "AUTOCORRECT_HOVER_MS" in SOURCE
    assert "clearTimeout(entry.hover)" in SOURCE


def test_the_document_editor_shows_the_same_underline_and_menu():
    # B04 beyond the popup: the document editor corrected a word with only a
    # toast (measured: no `.autocorrect-mark` after typing "teh "). documents.js
    # hands its correction to autocorrect.js (`autocorrectShow`), which draws the
    # underline over the CodeMirror view and offers Keep, Put back, Edit. Ctrl+Z
    # stays the document's own (its history step), so the entry is `native`.
    docs = (JS / "documents.js").read_text(encoding="utf-8")
    fn = docs[docs.index("function docAutocorrectAt(") :]
    fn = fn[: fn.index("\n}\n")]
    assert 'lazyScript("/js/autocorrect.js")' in fn
    assert "autocorrectShow(" in fn
    assert "function autocorrectShow(" in SOURCE
    show = SOURCE[SOURCE.index("function autocorrectShow(") :]
    show = show[: show.index("\n}\n")]
    assert "native: true" in show
    keys = SOURCE[SOURCE.index("Ctrl+Z or Backspace straight after") :]
    assert "entry.native" in keys[: keys.index("document.addEventListener(\"focusout\"")]
    # A word put back in the menu is not corrected again in the document.
    assert "autocorrectRefused" in fn
    assert "autocorrectShow(box, start," in fn
