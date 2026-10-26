"""One reader of date words and units (CHAT_PLAN "The deterministic
foundation", decision 46 and section 3's rule): no file outside
`ai/recognise.py` and `entry/timewords.py` compiles a date-word or unit
pattern, or tests a date word to turn it into a window.

The scan is F0's (`scratchpad/reader_count.py`). The count was 6 files when
F0 measured it and 9 on the head Brief 65 started from (Brief 39 added
`utilities`, `factgraph` and `insights`); after Brief 65 it is 1:
`ai/composer.py`'s `_DATE_CUE`, the engine's file, which scores a sentence as
dated and turns nothing into a value; ledger row 453 (2026-10-11) moved that
and its window pattern into the recogniser, so it is 0. The set below only shrinks: a new
reader fails this test, and a reader that delegates must leave the set here.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: The files still reading, each a row of `agent-remaining/f1-1010.md` to move.
STILL_READING: set[str] = set()


def _scan():
    spec = importlib.util.spec_from_file_location("reader_count", ROOT / "scratchpad" / "reader_count.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_no_file_but_the_recogniser_reads_dates_or_units():
    scan = _scan()
    found = scan.collect()
    readers = set()
    for rel, kinds in found.items():
        if rel in scan.ALLOWED:
            continue
        verdict = scan.VERDICT.get(rel, "")
        # A hand verdict of "not a reader" clears a pattern only when it says
        # what the pattern masks instead of reads (2026-10-26, the spellcheck's
        # unit mask: the browser cannot call the recogniser, and the mask turns
        # no word into a value).
        masked = verdict.startswith("not a reader") and "mask" in verdict
        if (kinds["pattern"] and not masked) or (kinds["keyword"] and verdict.startswith("reader")):
            readers.add(rel)
    assert readers == STILL_READING, (
        f"new readers: {sorted(readers - STILL_READING)} (read through ai/recognise.py instead); "
        f"gone: {sorted(STILL_READING - readers)} (take them out of STILL_READING)"
    )


def test_every_table_the_scan_finds_is_judged():
    scan = _scan()
    unjudged = [rel for rel, kinds in scan.collect().items()
                if rel not in scan.ALLOWED and kinds["table"] and rel not in scan.VERDICT]
    assert not unjudged, unjudged
