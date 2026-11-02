"""`composer_select._score`, pinned before it was split (cmpcc-1101).

Characterisation: for each case, every sentence's score after the call (it
sets one on each, zero for a sentence with nothing of the question) and the
sentences it returns, compared with `fixtures/composer/select_score_paths.json`
written by this code before the refactor. Scores are kept as `repr`, so a
change in the order of the float arithmetic shows. The cases reach every
branch: no sentence at all, no terms, a term met by its synonym, a kind word
beside a name, a title that holds every term, a category or tag that holds
one, a sentence that only names the subject, a "status" question's recency,
a connected note, and a note a newer one corrects when the question asks
about now. A difference here is a changed ranking, never a test to update.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from tessellate.ai import composer_select
from tessellate.ai.composer_read import read_note

TODAY = date(2026, 10, 6)
GOLDEN = Path(__file__).parent / "fixtures" / "composer" / "select_score_paths.json"


def _note(note_id: int, content: str, days_ago: int | None, **extra) -> dict:
    note = {"id": note_id, "content": content, **extra}
    if days_ago is not None:
        note["created_at"] = (TODAY - timedelta(days=days_ago)).isoformat()
    return note


NOTES = [
    _note(1, "# Harbor launch plan\n\nShip the mobile app to the public on the 14th of next month. Three gates before then: beta feedback closed, the onboarding rewrite merged, and the pricing page signed off.\n\n- [x] Beta invite list\n- [x] Crash reporting\n- [ ] Store listing copy", 30, category="Work", tags=["harbor"]),
    _note(2, "# Beta feedback, week 2\n\n41 testers active. The top complaint is the sign-up flow (nine fields). So, offline mode is hard to find.", 20, tags=["beta", "launch"]),
    _note(3, "# Dentist\n\nCheck-up booked for the 21st. Ask about the night guard. My teeth hurt after the dental clean.", 9, category="Health"),
    _note(4, "# Reading list\n\n- Designing Data-Intensive Applications\n- The Mom Test\n- A Pattern Language", 40),
    _note(5, "# Why the list felt slow\n\nIt was not the database. Every row re-measured its own height on scroll. Caching the height per row took a long list from 40ms a frame to 6.", 15),
    _note(6, "# Standup\n\nThe launch date is the 14th of next month.", 5),
    _note(7, "# Standup again\n\nThe launch date moved to the 21st of next month, a week later.", 1),
    _note(8, "Garden shed roof leaks in the north corner. The release of the shed paint is next week.", None),
    _note(9, "# Store listing\n\nStore listing copy. We decided the store listing leads with offline mode.", 3, connected=True),
    _note(10, "# Holiday ideas\n\nA trip to Porto in spring. Vacation days are booked for April.", 12, category="Travel"),
    _note(11, "# Dentist appointment moved\n\nMoved the dentist appointment from the 21st to the 28th.", 2),
]
VIEWS = [read_note(n, i) for i, n in enumerate(NOTES)]
TERMS = (
    [],
    ["launch"],
    ["launch", "date"],
    ["store", "listing"],
    ["list"],
    ["reading", "list"],
    ["dentist"],
    ["trip"],
    ["harbor"],
    ["slow", "list"],
    ["zebra"],
    ["beta", "launch", "pricing"],
)
SHAPES = ("count", "when", "status", "explain", "yesno", "list", "where", "who", "plain")


def _run(shape: str, terms: list[str], views: list, asks_now: bool) -> str:
    token = composer_select._ASKS_NOW.set(asks_now)
    try:
        kept = composer_select._score(shape, terms, views)
    finally:
        composer_select._ASKS_NOW.reset(token)
    every = " ".join(f"{s.note_id}.{s.order}={s.score!r}" for v in views for s in v.sentences)
    return f"{every} | kept {' '.join(f'{s.note_id}.{s.order}' for s in kept)}"


def cases() -> list[str]:
    rows = [_run("plain", ["launch"], [], False), _run("plain", ["launch"], [VIEWS[3], VIEWS[0]][:0], True)]
    for terms in TERMS:
        for shape in SHAPES:
            for asks_now in (False, True):
                rows.append(_run(shape, list(terms), VIEWS, asks_now))
        rows.append(_run("status", list(terms), VIEWS[5:], True))
        rows.append(_run("status", list(terms), [VIEWS[7]], False))
    return rows


def test_score_output_is_unchanged() -> None:
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    now = cases()
    assert len(now) == len(golden)
    for i, (got, want) in enumerate(zip(now, golden)):
        assert got == want, i
