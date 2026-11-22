"""L-world-class-410: the duplicate scan held every matching pair at once.

`GET /tidy` runs `find_duplicates`, and `find_duplicates` kept each pair the
scan yielded in a dict (`best`) to read each group's strongest score off it
afterwards. On a notebook whose notes share most of their words every pair
matches: 5,000 notes is 12.5 million pairs, measured as RSS 330 MB to 1.7 to
2.0 GB in 35 s after opening the graph tab, freed when the request ended
(tracemalloc: 119 MB at duplicates.py:291 at the first snapshot, still climbing). The
strongest score is now kept per group while the groups merge, so memory
follows the notes, not the pairs. Counts and `tracemalloc`, never time.
"""

from __future__ import annotations

import tracemalloc

from tessellate.core.database import Entry
from tessellate.entry import duplicates

BASE = " ".join(f"word{n}" for n in range(30))


def _seed(session, count: int) -> None:
    for n in range(count):
        session.add(Entry(content=f"{BASE} unique{n}"))
    session.commit()


def test_scan_memory_does_not_follow_the_pair_count(session):
    notes = 1000  # 499,500 matching pairs, all above the threshold
    _seed(session, notes)
    tracemalloc.start()
    try:
        groups = duplicates.find_duplicates(session)
        _current, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert len(groups) == 1 and len(groups[0]["entries"]) == notes
    # One tuple, two ints, a float and a dict slot a pair was about 240 bytes:
    # about 110 MB here. The notes and one block of the product cost under 35 MB.
    assert peak < 60 * 1024 * 1024, peak


def test_group_similarity_is_its_strongest_pair(session):
    session.add(Entry(content=f"{BASE} a"))
    session.add(Entry(content=f"{BASE} b"))  # 30 shared of 32: 0.9375
    session.add(Entry(content=f"{BASE} a"))  # same text as the first: 1.0
    session.add(Entry(content="nothing in common with the rest of them at all"))
    session.commit()
    groups = duplicates.find_duplicates(session)
    assert len(groups) == 1
    assert groups[0]["similarity"] == 1.0
    assert len(groups[0]["entries"]) == 3
