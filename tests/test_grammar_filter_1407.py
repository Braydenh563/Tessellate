"""Harper's false positives, filtered app-side (INBOX 1407, owner 2026-10-27).

"A lot of the suggestions are inaccurate." Measured: Harper 2.13.0 and 3.0.0
give the same false positives as the vendored 2.10.0, so upgrading was not the
answer; the page filters. `tests/grammar_fixture_1407.json` holds 33 clean
lines (a file name, a tech word, "back to normal") and 8 planted errors, run
through `tests/_grammar_harness.js` (the shipped functions plus the real
worker). Before: 20 findings on 15 of the 33 clean lines, 8 of 8 planted
errors caught. The ratchets: zero on the clean lines, every planted error
still caught.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tests" / "_grammar_harness.js"
FIXTURE = ROOT / "tests" / "grammar_fixture_1407.json"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node is not available")


@pytest.fixture(scope="module")
def measured() -> dict:
    out = subprocess.run(
        ["node", str(HARNESS), str(ROOT), str(FIXTURE), "{}"],
        capture_output=True, text=True, timeout=180, check=False,
    )
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def _shown(item: dict) -> str:
    return f"{item['text']!r} -> " + "; ".join(f"{f['rule']}/{f['kind']} {f['text']!r}: {f['message']}" for f in item["findings"])


@pytest.mark.parametrize("tag", ["to-too", "file", "tech", "plain"])
def test_each_false_positive_class_is_clean(measured, tag) -> None:
    items = [item for item in measured["clean"] if item["tag"] == tag]
    assert items
    bad = [_shown(item) for item in items if item["findings"]]
    assert not bad, "\n".join(bad)


def test_every_planted_error_is_still_caught(measured) -> None:
    missed = []
    for item in measured["planted"]:
        expect = item["expect"].lower()
        if not any(expect in f["text"].lower() or f["text"].lower() in expect for f in item["findings"]):
            missed.append(_shown(item))
    assert not missed, "\n".join(missed)
