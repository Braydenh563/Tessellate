"""L133: the learning loop's reads on a notebook past test size.

3,000 notes and 3,000 corrections (refiles across 12 categories), then each
read the filing path makes is timed on a fixed seed. The numbers measured on
2026-11-14: corrections 17 ms, boosts 14, filing_accuracy 78, excluded_categories 22,
filing_evidence 31. The budget is one second each (over ten times the slowest), so a read that
turns into a per-note pass fails here rather than on someone's notebook."""

from __future__ import annotations

import time

from tessellate.ai import learning
from tessellate.entry import manager

CATEGORIES = [f"Cat{i}" for i in range(12)]


def _seed(session) -> str:
    for i in range(3000):
        entry = manager.create_entry(session, f"# Note {i}\n\nA note about {CATEGORIES[i % 12].lower()} and topic{i % 40} with some words.")
        learning.record(session, kind="refile", subject={"entry_id": entry.id}, from_value=CATEGORIES[i % 12], to_value=CATEGORIES[(i + 1) % 12], excerpt=entry.content[:80])
    session.commit()
    return "A note about cat3 and topic7 with some words."


def _timed(fn) -> float:
    start = time.perf_counter()
    fn()
    return time.perf_counter() - start


def test_the_filing_reads_stay_fast_on_3000_notes_and_corrections(session):
    text = _seed(session)
    spent = {
        "corrections": _timed(lambda: learning.corrections(session, "refile")),
        "boosts": _timed(lambda: learning.boosts(session, "filing")),
        "filing_accuracy": _timed(lambda: learning.filing_accuracy(session)),
        "excluded_categories": _timed(lambda: learning.excluded_categories(session, text)),
        "filing_evidence": _timed(lambda: learning.filing_evidence(session, text)),
    }
    slow = {k: round(v, 3) for k, v in spent.items() if v > 1.0}
    assert not slow, slow
