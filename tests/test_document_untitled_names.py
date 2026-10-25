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
