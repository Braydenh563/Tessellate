"""Prose false positives from audit 1102 (DX19), one pinned test per sentence.

Three classes, measured by `tests/_grammar_harness.js` (the shipped rule
engine and filter plus the real Harper worker) on `grammar_fixture_1102.json`:
the `!` of an image (`![alt](src)`) read as a space before punctuation, Harper's
"it's" read as a possessive before a compound adjective ("it's colour coded"),
and a sentence-initial noun ("Callout kinds", "Backup files") read as a phrasal
verb. Before: 6 findings on 9 clean lines. The ratchets: zero on the clean lines
and every planted error still caught.
"""

from __future__ import annotations
from tests._app_js import frontend_text

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tests" / "_grammar_harness.js"
FIXTURE = ROOT / "tests" / "grammar_fixture_1102.json"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node is not available")


@pytest.fixture(scope="module")
def measured() -> dict:
    out = subprocess.run(
        ["node", str(HARNESS), str(ROOT), str(FIXTURE), "{}"],
        capture_output=True, text=True, timeout=180, check=False,
    )
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


_FIXTURE = json.loads(FIXTURE.read_text(encoding="utf-8"))


def _shown(item: dict) -> str:
    return f"{item['text']!r} -> " + "; ".join(f"{f['rule']}/{f['kind']} {f['text']!r}: {f['message']}" for f in item["findings"])


@pytest.mark.parametrize("sentence", [item["text"] for item in _FIXTURE["clean"]], ids=lambda s: s[:40])
def test_a_clean_sentence_has_no_finding(measured, sentence) -> None:
    item = next(i for i in measured["clean"] if i["text"] == sentence)
    assert not item["findings"], _shown(item)


@pytest.mark.parametrize("sentence", [item["text"] for item in _FIXTURE["planted"]], ids=lambda s: s[:40])
def test_a_planted_error_is_still_caught(measured, sentence) -> None:
    item = next(i for i in measured["planted"] if i["text"] == sentence)
    expect = item["expect"].lower()
    assert any(expect in f["text"].lower() or f["text"].lower() in expect for f in item["findings"]), _shown(item)


def test_a_misspelling_row_names_its_nearest_word() -> None:
    """"libary" and "tomorow" showed only "not in the dictionary" until the row
    was opened. The row now says "Did you mean ...", from one edit only."""
    source = frontend_text("documents.js")
    assert "docSpellGuesses.hint = (finding)" in source
    line = source[source.index("function docFindingLine("):]
    line = line[: line.index("\n}\n")]
    assert 'variant === "row" ? docSpellGuesses.hint(finding)' in line
    assert "Did you mean" in line
    guesses = source[source.index("function docSpellGuesses("):]
    assert "!quick && near.length < DOC_TWO_EDIT_FLOOR" in guesses[:1200], "the hint must not pay for two edits"
