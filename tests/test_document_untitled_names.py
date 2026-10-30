"""A new document needs no name (INBOX 739, the owner: "auto naming of the
whiteboards, mindmaps and documents like untitled #").

Boards and maps name themselves in `wbUntitledNames`; documents did, until
now, all become "Untitled", which the list cannot tell apart. The naming rule
is a pure function between markers in documents.js, run in node here.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

DOCUMENTS_JS = Path(__file__).resolve().parents[1] / "frontend" / "js" / "documents.js"
BEGIN = "// DOC-UNTITLED-BEGIN"
END = "// DOC-UNTITLED-END"


def source() -> str:
    text = DOCUMENTS_JS.read_text(encoding="utf-8")
    start, stop = text.find(BEGIN), text.find(END)
    assert start != -1 and stop > start, "DOC-UNTITLED markers are missing from documents.js"
    return text[start:stop]


def run(titles: list[str]) -> str:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    script = source() + f"\nprocess.stdout.write(docUntitledName({json.dumps(titles)}));"
    return subprocess.run([node, "-e", script], capture_output=True, text=True, check=True).stdout


def test_first_document_has_no_number():
    assert run([]) == "Untitled document"
    assert run(["Meeting notes", "Untitled"]) == "Untitled document"


def test_second_document_is_number_two():
    # dog1-1025 item 16: the bare name counts as number one.
    assert run(["Untitled document"]) == "Untitled document 2"
    assert run(["Untitled document", "Untitled document 2"]) == "Untitled document 3"
    assert run(["Untitled document 1"]) == "Untitled document 2"


def test_next_free_number_follows_the_highest():
    assert run(["Untitled document 1", "Untitled document 3"]) == "Untitled document 4"


def test_case_and_spacing_do_not_hide_a_number():
    assert run(["  untitled DOCUMENT 7 "]) == "Untitled document 8"


def test_creation_paths_use_the_rule():
    text = DOCUMENTS_JS.read_text(encoding="utf-8")
    assert text.count("docNextName()") >= 3, "template, first keystroke, empty title (a blank draft names itself on first edit)"


def test_only_an_unnamed_empty_document_counts_as_untouched():
    """dog3-1026 D20: leaving bins a document the app named and nobody wrote in."""
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    cases = [["Untitled document", ""], ["Untitled document 7", " \n"], ["Untitled document", "a word"], ["Essay two", ""], ["untitled document 3", ""], ["Untitled", ""], ["", ""], ["", "text"]]
    script = source() + f"\nprocess.stdout.write(JSON.stringify({json.dumps(cases)}.map(([t, x]) => docIsUntouched(t, x))));"
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, check=True).stdout
    assert json.loads(out) == [True, True, False, False, True, True, True, False]


def test_an_emptied_title_waits_for_the_field_to_be_left():
    """D17 (audit 1028): clearing the title to retype it used to autosave the
    document as "Untitled document N" while the field stayed blank, so the
    list and the field disagreed. The autosave keeps the stored title; leaving
    the field, or a save by hand, fills it."""
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    text = DOCUMENTS_JS.read_text(encoding="utf-8")
    start = text.index("function docFillBlankTitle()")
    fill = text[start:text.index("\n}\n", start) + 3]
    save = text[text.index("async function docSaveOnce(silent)"):]
    save = save[:save.index("const content = docText();")]
    assert "if (!silent) docFillBlankTitle();" in save
    assert "currentDoc.title || docNextName()" in save
    assert 'addEventListener("blur", () => { if (docFillBlankTitle()) markDocDirty(); })' in text
    script = source() + fill + """
const field = { value: "" };
const $ = () => field;
let docs = [{ title: "Untitled document" }, { title: "Trip" }];
const docNextName = () => docUntitledName(docs.map((d) => d.title));
const out = [];
let currentDoc = { title: "Trip" };
out.push([docFillBlankTitle(), field.value]);
currentDoc = { title: "Untitled document 4" }; field.value = "  ";
out.push([docFillBlankTitle(), field.value]);
field.value = "Kept";
out.push([docFillBlankTitle(), field.value]);
process.stdout.write(JSON.stringify(out));
"""
    got = subprocess.run([node, "-e", script], capture_output=True, text=True, check=True).stdout
    assert json.loads(got) == [[True, "Untitled document 2"], [True, "Untitled document 4"], [False, "Kept"]]


def test_a_failed_drop_puts_the_document_back_in_the_list():
    """D36 (audit 1028): a refused DELETE left the row on the server while
    the list forgot it."""
    text = DOCUMENTS_JS.read_text(encoding="utf-8")
    start = text.index("async function docDropIfUntouched(")
    body = text[start: text.index("\n}\n", start)]
    assert '.catch(() => { docs = [doc, ...docs]; })' in body
    assert body.index("docs = [doc, ...docs]") < body.index("renderDocList()")


def test_a_failed_save_says_so_once_with_try_again():
    """D34 (audit 1028): a failed save was two words in the status bar."""
    text = DOCUMENTS_JS.read_text(encoding="utf-8")
    start = text.index("async function docSaveOnce(silent)")
    body = text[start: text.index("\n}\n", start)]
    assert "if (!docSaveFailedSaid) {" in body and 'action: ["Try again", () => saveDocument({ silent: false })]' in body
    assert body.index("docSaveFailedSaid = false;") < body.index('$("doc-saved").textContent = "Saved";')
