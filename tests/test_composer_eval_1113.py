"""The floors for the five composer eval sets CHAT_PLAN section 4 named (L-chat-22): time windows,
recall, social turns, out-of-domain questions and how-to questions. Each set is a fixture in
`fixtures/composer/` written by `scripts/composer_fixtures_1113.py` (every expected value worked
out from the row itself, never by running the engine), read by a `run_*` and a `*_summary` in
`tests/_composer_eval.py`. A set the engine misses a floor on is a LEDGER row, and its test asserts
the measured number as a ratchet that only goes up."""

from __future__ import annotations

from tests import _composer_eval


def test_every_time_phrase_reads_to_its_exact_window():
    got = _composer_eval.windows_summary(_composer_eval.run_windows())
    assert got["rows"] == 60
    #: Includes the forms measured as missed ("since March", "the week before last", "on 3 March" read
    #: as past) and the regression that "last friday" is the past Friday.
    assert got["exact"] == 1.0, got["missed"]
    phrases = {r["phrase"] for r in _composer_eval.run_windows()}
    assert {"since March", "the week before last", "on 3 March", "last friday"} <= phrases
