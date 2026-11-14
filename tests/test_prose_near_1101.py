"""Typing in a long document reads the paragraph it edits (prose-1101).

Before: every key ran the prose rules and the skip mask over the whole 14,000
character window, or over the whole text when it held no blank line (notes made
of lines): at 4x in a 5,000-line document that was 62 to 89 ms a key, and 362 to
379 ms in the one with no blank lines. Now a key's pass keeps every finding
outside the edited paragraph and reads that paragraph alone; a full pass follows
once the writer pauses (`docProse.settle`), so what settles is the full pass's.

The harness (`tests/_prose_near_harness.js`) cuts the page's own functions out
of the source and compares, edit by edit, the keystroke pass with the old full
pass on the same text.
"""

from __future__ import annotations
from tests._app_js import frontend_text

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tests" / "_prose_near_harness.js"
JS = ROOT / "frontend" / "js"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node is not available")

SENTENCES = [
    "The committee reviewed the proposal and noted that the schedule depended on funding.",
    "Each team will recieve a short brief before the meeting on Thursday afternoon.",
    "See `parse_document` and https://example.com/a/b for the longer background.",
    "Their is a risk that the plan slips, so the board asked for a weekly report.",
    "The budget for the second quarter was approved without further discussion.",
    "A note called [[Quarterly plan]] holds the detail, and teh summary is below.",
]


def _paragraph(i: int) -> str:
    return " ".join(SENTENCES[(i + k) % len(SENTENCES)] for k in range(3)) + f" Item {i}."


def _prose() -> str:
    parts = ["# Annual report", ""]
    for i in range(1, 60):
        parts.append(_paragraph(i))
        parts.append("")
        if i == 10:
            parts += ["- first point about the plan", "- second point with a tpyo", "- third point", ""]
        if i == 20:
            parts += ["```python", "x = teh(1)", "", "y = recieve(2)", "```", ""]
        if i == 30:
            parts += ["## Part three", ""]
        if i == 40:
            long = " ".join(["word"] * 60) + "."
            parts += [long, ""]
    return "\n".join(parts)


def _flat() -> str:
    """Notes that are all lines, no blank line anywhere (the case that made the window the whole text)."""
    return "\n".join(f"{SENTENCES[i % len(SENTENCES)]} Line {i}." for i in range(420))


def _typing(find: str, offset: int, text: str, label: str) -> list[dict]:
    return [{"find": find, "offset": offset + n, "remove": 0, "insert": ch, "label": f"{label} {ch!r}"} for n, ch in enumerate(text)]


def _scenario() -> dict:
    prose_edits = (
        _typing("Item 25.", 0, "x", "end of a paragraph")
        + _typing("Item 31.", -6, "qz ", "inside a paragraph")
        + _typing("Item 12.", -20, "recieve", "a typo typed")
        + [{"find": "Each team will recieve", "offset": 15, "remove": 7, "insert": "receive", "label": "typo fixed"}]
        + [{"find": "Their is a risk", "offset": 0, "remove": 5, "insert": "There", "label": "word replaced"}]
        + [{"find": "- second point with a tpyo", "offset": 25, "remove": 0, "insert": "s", "label": "in a list item"}]
        + [{"find": "## Part three", "offset": 13, "remove": 0, "insert": "s", "label": "in a heading"}]
        + [{"find": "Item 5.", "offset": 0, "remove": 0, "insert": "\n\n", "label": "a blank line typed"}]
        + [{"find": "Item 45.", "offset": 0, "remove": 0, "insert": "`", "label": "a backtick typed"}]
        + [{"find": "x = teh(1)", "offset": 4, "remove": 0, "insert": "z", "label": "inside a fence"}]
        + [{"find": "# Annual report", "offset": 15, "remove": 0, "insert": "s", "label": "in the first heading"}]
        + [{"find": "Item 58.", "offset": 8, "remove": 0, "insert": " end", "label": "at the very end"}]
    )
    flat_edits = (
        _typing("Line 100.", 0, "ab", "mid flat line")
        + _typing("Line 7.", -8, "teh ", "typo in a flat line")
        + [{"find": "Line 150.", "offset": 0, "remove": 1, "insert": "", "label": "a delete"}]
    )
    return {
        "dictionary": ["tessellate"],
        "docs": [
            {"name": "prose", "text": _prose(), "edits": prose_edits},
            {"name": "flat", "text": _flat(), "edits": flat_edits, "window": {"from": 14000, "to": 16000}},
        ],
    }


@pytest.fixture(scope="module")
def ran(tmp_path_factory) -> dict:
    path = tmp_path_factory.mktemp("near") / "scenario.json"
    path.write_text(json.dumps(_scenario()), encoding="utf-8")
    out = subprocess.run(
        ["node", str(HARNESS), str(ROOT), str(path)], capture_output=True, text=True, timeout=180, check=False
    )
    assert out.returncode == 0, out.stderr
    return {doc["name"]: doc for doc in json.loads(out.stdout)["docs"]}


def test_the_fixtures_are_long_enough_for_the_keystroke_pass(ran) -> None:
    for doc in ran.values():
        assert doc["steps"][0]["textLength"] >= 8000


@pytest.mark.parametrize("name", ["prose", "flat"])
def test_each_keystroke_pass_finds_what_the_full_pass_finds(ran, name) -> None:
    wrong = [
        f"{step['label']}: only near {step['only_near']}, only full {step['only_full']}"
        for step in ran[name]["steps"]
        if not step["equal"]
    ]
    assert not wrong, "\n".join(wrong)


def test_a_key_inside_a_paragraph_reads_the_paragraph_not_the_window(ran) -> None:
    small = [s for s in ran["prose"]["steps"] if 0 < s["zone"] < 1500]
    # Typed letters, a fix and a replaced word are paragraph edits; the blank line, the backtick,
    # the fence (its neighbours could change) take the full pass.
    assert len(small) >= 17, [(s["label"], s["zone"]) for s in ran["prose"]["steps"]]
    full = {s["label"] for s in ran["prose"]["steps"] if s["zone"] > 8000}
    assert full == {"a blank line typed", "a backtick typed", "inside a fence"}, full
    flat = ran["flat"]["steps"]
    assert all(0 < s["zone"] < 1000 for s in flat), [(s["label"], s["zone"]) for s in flat]
    assert all(s["dirty"] for s in small)


def test_the_pause_runs_the_full_pass_once_and_it_is_the_old_result(ran) -> None:
    for name in ("prose", "flat"):
        settled = ran[name]["settled"]
        assert settled["ran"] == 1 and settled["equal"] and settled["dirty"] is False, (name, settled)


def test_a_window_without_blank_lines_is_cut_at_a_line_not_the_whole_text(ran) -> None:
    window = ran["flat"]["window"]
    assert window["atLineStart"] and window["atLineEnd"]
    assert window["to"] - window["from"] < 2 * 14000 + 200
    assert window["from"] > 0, window


def test_the_page_keeps_one_pass_per_key_and_the_settle_wiring() -> None:
    docs = frontend_text("documents.js")
    assert re.search(r"docProse\.typing = true;\s*try \{\s*renderDocProse\(\);", docs)
    assert "docProseSkipMask.memo" in docs and "if (this.dirty) renderDocProse();" in docs
