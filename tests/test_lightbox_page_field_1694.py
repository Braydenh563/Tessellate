"""INBOX 1694 (b), the owner: page numbers "must be typeable and offer a quick dropdown". The lightbox's zoom readout
was a field already; its "Page 3 of 12" label was still text. It is now a `valueField` (min 1, max the page count),
Enter jumps through `setDocPage`, and the dropdown lists pages (all up to twelve, else twelve spread across)."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

SRC = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "lightbox-view.js").read_text(encoding="utf-8")


def _block(start: str, length: int = 1400) -> str:
    return SRC[SRC.index(start) :][:length]


def test_the_page_label_is_a_value_field_over_the_page_count():
    block = _block("const drawPageField = ")
    assert "valueField(pageLabel" in block
    assert "min: 1" in block
    assert "max: () => docPageCount" in block
    assert "onCommit: (n) => setDocPage(n - 1)" in block
    assert "Page ${v} of ${docPageCount}" in block


def test_the_chips_sync_moves_the_field_and_redraws_it_when_the_count_changes():
    sync = _block("function syncPageChips()", 900)
    assert "pageFieldCount !== docPageCount" in sync
    assert "pageField?.set(docPage + 1)" in sync
    assert "presets: pagePresets(docPageCount)" in _block("const drawPageField = ")


def test_the_label_still_hides_with_the_page_controls_and_is_announced():
    assert "const pageControls = [pagePrevBtn, pageLabel, pageNextBtn];" in SRC
    #: An input's value change is not read out, so a status line beside the field says the page.
    status = _block("const pageStatus", 400)
    assert "visually-hidden" in status and 'setAttribute("role", "status")' in status


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
@pytest.mark.parametrize("pages,expected", [(1, [1]), (5, [1, 2, 3, 4, 5]), (12, list(range(1, 13)))])
def test_a_short_file_lists_every_page(pages, expected):
    assert _presets(pages) == expected


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_a_long_file_lists_twelve_spread_pages_with_the_first_and_last():
    rows = _presets(400)
    assert len(rows) == 12 and rows[0] == 1 and rows[-1] == 400
    assert rows == sorted(set(rows))


def _presets(pages: int) -> list[int]:
    start = SRC.index("const pagePresets = ")
    fn = SRC[start : SRC.index("\n  };\n", start) + 5]
    code = f"{fn};process.stdout.write(JSON.stringify(pagePresets({pages}).map((r) => r.value)))"
    return json.loads(subprocess.run(["node", "-e", code], capture_output=True, text=True, check=True).stdout)
