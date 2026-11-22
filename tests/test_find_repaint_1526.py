"""The findings stay put while typing, and answers repaint once a frame (INBOX 1526).

Before: `docFindingsPlugin` rebuilt its underlines from the stale offsets on
every edit, dropped every one that had moved, and drew them again only when
`renderDocProse` ran about 150 ms later; each grammar answer then dispatched a
repaint of its own (97 renders for 50 keys, about 9 ms each at 4x CPU). Now the
findings are moved through the edit's changes, and a repaint that would draw
what is already drawn is not sent, and answers share a beat.

The harness (`tests/_find_repaint_harness.js`) cuts the page's own plugin and
repaint call out of the source and runs them against a small fake of the engine.
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
HARNESS = ROOT / "tests" / "_find_repaint_harness.js"
JS = ROOT / "frontend" / "js"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node is not available")


@pytest.fixture(scope="module")
def ran() -> dict:
    out = subprocess.run(["node", str(HARNESS), str(ROOT)], capture_output=True, text=True, timeout=60, check=False)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def test_underlines_keep_their_words_across_an_edit_before_them(ran) -> None:
    kept = ran["kept"]
    assert kept["before"] == ["Teh", "recieve", "the the"]
    assert kept["after"] == kept["before"], kept
    assert all(kept["found"]), kept


def test_an_edit_inside_a_finding_drops_only_that_finding(ran) -> None:
    assert ran["kept"]["edited"] == ["Teh", "the the"], ran["kept"]


def test_a_letter_typed_at_a_findings_end_does_not_move_or_stretch_it(ran) -> None:
    # "Teh" was at 0 to 3 before the 3-character prefix, so it is 3 to 6 now and stays 3 to 6.
    assert ran["kept"]["tail"][0] == [3, 6], ran["kept"]["tail"]


def test_answers_in_one_frame_are_one_dispatch(ran) -> None:
    r = ran["repaint"]
    assert r["beforeFrame"] == 0 and r["frames"] == 1, r
    assert r["afterFrame"] == 1, r


def test_a_repaint_that_draws_what_is_drawn_is_not_sent(ran) -> None:
    r = ran["repaint"]
    assert r["unchanged"] == 1, r
    assert r["changed"] == 2, r
    assert r["immediate"] == 3, r


def test_the_page_batches_the_answers_only() -> None:
    docs = frontend_text("documents.js") + (JS / "documents-view.js").read_text(encoding="utf-8")
    assert "docCmRepaintFindings(again)" in docs
    assert re.search(r"docProse\.remap\(update\.changes\)", docs)
