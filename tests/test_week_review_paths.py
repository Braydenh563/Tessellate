"""`composer_voice.week_review`, pinned before it was split (cmpcc-1101).

Characterisation: every case's whole result (text, parts, grounding,
sources, key) is compared with `fixtures/composer/week_review_paths.json`,
written by this code before the refactor. The cases reach every branch: no
note this week, one note, two (no category line), one and two top
categories, standouts by category then the rest and cut at four, a note with
nothing to lead with, open tasks cut at three, loose notes with and without
`unlinked`. A difference here is a changed review, never a test to update.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from tessellate.ai import composer_voice

TODAY = date(2026, 10, 6)
GOLDEN = Path(__file__).parent / "fixtures" / "composer" / "week_review_paths.json"


def _note(note_id: int, content: str, days_ago: int, **extra) -> dict:
    return {"id": note_id, "content": content, "created_at": (TODAY - timedelta(days=days_ago)).isoformat(), **extra}


WEEK = [
    _note(1, "# Harbor launch plan\n\nShip the mobile app to the public on the 14th of next month.\n\n- [x] Beta invite list\n- [ ] Store listing copy\n- [ ] Pricing page sign off", 1, category="Work"),
    _note(2, "# Beta feedback\n\n41 testers active. The top complaint is the sign-up flow with nine fields.", 2, category="Work"),
    _note(3, "# Dentist\n\nCheck-up booked for the 21st, ask about the night guard.\n\n- [ ] Call to confirm", 3, category="Health"),
    _note(4, "# Lisbon\n\nAlfama has the walk-everywhere feel, but the hills are steep and long.", 4, category="Travel"),
    _note(5, "# Porto\n\nRibeira at sunset, and a port lodge tour across the bridge in Gaia.", 5, category="Travel"),
    _note(6, "Garden shed roof leaks in the north corner after the rain.", 0),
    _note(7, "# Shopping\n\n- [ ] Milk\n- [ ] Bread\n- [x] Eggs", 2, category="Home"),
    _note(8, "# Old plan\n\nThis note is from last month and is not in the week at all.", 20, category="Work"),
    _note(9, "# Sync rewrite\n\nThe sync rewrite now keeps both versions and asks, merged behind a flag.", 6, category="Work"),
]

LONG = "word " * 60


def cases() -> dict[str, dict]:
    run = composer_voice.week_review
    return {
        "none": run([], today=TODAY),
        "none_old_only": run([WEEK[7]], today=TODAY),
        "one": run([WEEK[0]], today=TODAY),
        "one_untitled": run([WEEK[5]], today=TODAY),
        "two_no_category_line": run(WEEK[:2], today=TODAY),
        "three_one_category": run([WEEK[0], WEEK[1], WEEK[8]], today=TODAY),
        "three_no_category": run([WEEK[5], _note(10, "Plain words about the bike chain, it needs oil soon.", 1), _note(11, "Another plain one about the kettle descaling this weekend.", 2)], today=TODAY),
        "full_week": run(WEEK, today=TODAY),
        "full_week_unlinked": run(WEEK, today=TODAY, unlinked={2, 4, 6, 7, 9, 99}),
        "unlinked_empty": run(WEEK, today=TODAY, unlinked=set()),
        "unlinked_none_this_week": run(WEEK, today=TODAY, unlinked={8}),
        "title_only_alone": run([_note(12, "# Just a heading", 1, category="Work")], today=TODAY),
        "title_only_no_lead": run([_note(12, "# Just a heading", 1, category="Work"), WEEK[1], WEEK[2]], today=TODAY),
        "long_lead_clipped": run([_note(13, "# Long\n\nThis sentence is far too long to fit. " + LONG, 1), _note(14, "# Tasks only\n\n- [x] Done one\n- [ ] Open " + LONG, 2)], today=TODAY),
        "only_done_tasks": run([_note(15, "# Done list\n\n- [x] Paid the bill\n- [x] Sent the form", 1, category="Home"), _note(16, "# Short\n\nToo short.", 2, category="Home"), WEEK[2]], today=TODAY),
    }


def _plain(value: object) -> object:
    return json.loads(json.dumps(value, default=str))


def test_week_review_output_is_unchanged() -> None:
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    now = _plain(cases())
    assert sorted(now) == sorted(golden)
    for name in golden:
        assert now[name] == golden[name], name
