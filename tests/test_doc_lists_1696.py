"""List styles in the documents editor, kept in the markdown (INBOX 1696 cc).

The owner: "can there be different types of dot points or numbered lists??
like different styles?? what about other code mirror things??" and, in the
screenshot, "- Wizard covers: ..." showing a raw dash among rendered bullets.
The marker is the style (DOCUMENTS_PLAN decision 40), so the export and the
other views read it; the live view, the List and Numbered menus and the paste
fix share one block (`docLists`, documents-cm.js), run here against stubs.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


@pytest.fixture(scope="module")
def r() -> dict:
    done = subprocess.run(["node", str(ROOT / "tests" / "_doc_lists_harness.js")], capture_output=True, text=True, check=True)
    return json.loads(done.stdout)


def test_the_marker_is_the_style(r):
    assert r["bulletStyles"] == ["disc", "circle", "square", "dash", "disc", "circle", "dash"]
    assert r["parsed"] == [["ordered", "decimal"], ["ordered", "paren"], ["ordered", None], ["bullet", "disc"], None]


def test_letters_and_roman_numerals_are_lists_only_as_a_run(r):
    assert r["alphaRun"] == ["alpha"] * 3
    assert r["romanRun"] == ["roman"] * 5
    assert r["alphaThroughI"] == ["alpha"] * 10  # a to j: the i continues the letters, it does not start numerals
    assert r["romanAlone"] == ["roman"]
    assert r["lonely"] == [None, None, None]


def test_a_style_change_is_per_list_and_keeps_nesting_and_tasks(r):
    assert r["square"] == {"range": [1, 4], "lines": ["+ one", "+ two", "  - nested", "+ three"]}
    assert r["dash"] == ["-  one", "-  two", "  - nested", "-  three"]
    assert r["taskKept"] == ["- [ ] a", "* b"]
    assert r["looseList"] == ["+ a", "", "+ b"]
    assert r["nestedOnly"] == ["   * sub", "   * sub two"]


def test_a_list_next_to_another_kind_is_left_alone(r):
    """Measured live: restyling `1. one` once took the dot lists above and below it (a blank line is not the end of a loose list, a changed marker is)."""
    assert r["neighbourNumbers"] == {"from": 5, "to": 6, "lines": ["i. x", "ii. y"]}
    assert r["neighbourDots"] == {"from": 0, "to": 1, "lines": ["+ a", "+ b"]}
    assert r["neighbourBracket"] == {"from": 8, "to": 9, "lines": ["a. p", "b. q"]}


def test_numbered_styles_renumber_from_one(r):
    assert r["roman"] == ["i. one", "ii. two", "iii. three"]
    assert r["alpha"] == ["a. one", "b. two", "c. three"]
    assert r["paren"] == ["1) one", "2) two"]
    assert r["backToDots"] == ["- one", "- two", "- three"]
    assert r["newList"] == ["1. alpha", "", "2. beta"]


def test_a_pasted_look_alike_marker_at_a_line_start_becomes_a_dash(r):
    assert r["paste"][0] == "- one\n- two\n- three"
    assert r["paste"][1] == "- a\n- b\n- c\n- d\n- e"
    assert r["paste"][2] == "  - indented"
    assert r["paste"][3] == "no marker • inside stays"
    assert r["paste"][4] == "•nospace"
    assert r["paste"][5] == "x\n- y"


def test_the_first_pasted_line_is_a_line_start_only_at_a_line_start(r):
    assert r["pasteMid"] == "• first stays\n- second goes"
    assert r["pasteEvent"] == {"prevented": True, "inserted": "- one\n- two"}
    assert r["pasteEventMid"] == {"prevented": False, "inserted": None}
    assert r["pasteEventPlain"] == {"prevented": False, "inserted": None}


def test_each_button_has_a_menu_of_its_styles_that_writes_through_the_editor(r):
    assert [m["label"] for m in r["menus"]] == ["Dot point styles", "Numbering styles"]
    assert [len(m["rows"]) for m in r["menus"]] == [4, 4]
    assert r["menus"][0]["rows"][0].endswith("Dots") and r["menus"][1]["rows"][3].endswith("Roman numerals")
    assert r["menuSquare"] == "+ a\n+ b\n\nrest"
    assert r["menuRoman"] == "i. a\nii. b"
    assert r["menuNew"] == "a. one\nb. two"
    assert r["undoBreaks"] == r["finished"] == 3  # each pick is one undo step
    assert r["mountedTwice"] == 2  # mounting again adds nothing


def test_the_live_view_draws_the_style_of_each_marker():
    js = (ROOT / "frontend" / "js" / "documents-cm.js").read_text(encoding="utf-8")
    assert "docLists.bulletStyle(line.text)" in js and "new DocBulletWidget(style)" in js
    assert 'name === "Paragraph" && node.node.parent?.name === "Document"' in js
