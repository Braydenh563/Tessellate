"""The dashboard's day digest (CHAT_PLAN section 2, the dashboard row): due,
open questions, what changed and quiet topics, composed by the engine with
no model, every line a quoted span or a count (the row's measure).
`ai/day_digest.py`, `GET /insights/day`, `dashboard.js` `renderDigestWidget`."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from tests._app_js import with_pieces

from tessellate.ai import day_digest
from tessellate.core.database import Category, DerivedFact, Entry, Reminder

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 10, 14, 0, tzinfo=timezone.utc)
NAIVE = NOW.replace(tzinfo=None)
_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}


def _numbers(text: str) -> list[int]:
    found = [int(n) for n in re.findall(r"\d+", text)]
    found += [_WORDS[w] for w in re.findall(r"[a-z]+", text.lower()) if w in _WORDS]
    return found


def _notebook(session):
    fit = Category(name="Fitness")
    session.add(fit)
    session.flush()
    old = NAIVE - timedelta(days=45)
    for text in ("Squat day", "Deadlift cues", "Run 5k"):
        session.add(Entry(content=text, category_id=fit.id, created_at=old, updated_at=old))
    fresh = Entry(content="# Harbor deposit\nPaid 40 dollars. Should we book the boat for May?",
                  created_at=NAIVE - timedelta(hours=3), updated_at=NAIVE - timedelta(hours=3))
    edited = Entry(content="Garden plan", created_at=NAIVE - timedelta(days=9), updated_at=NAIVE - timedelta(hours=1))
    session.add_all([fresh, edited])
    session.flush()
    session.add(DerivedFact(entry_id=fresh.id, kind="question", text="Should we book the boat for May?",
                            span_start=34, span_end=66, model="local", confidence=0.9))
    session.add_all([
        Reminder(text="Call Sam about the deposit", due_at=NAIVE + timedelta(hours=2)),
        Reminder(text="Renew the boat licence", due_at=NAIVE - timedelta(days=2)),
        Reminder(text="Dentist", due_at=NAIVE + timedelta(days=3)),
        Reminder(text="Done already", due_at=NAIVE, done=True),
    ])
    session.commit()


def test_every_line_is_a_quoted_span_or_a_count(session):
    _notebook(session)
    lines = day_digest.compose(session, NOW)["lines"]
    assert {line["part"] for line in lines} == {"due", "questions", "changed", "quiet"}
    sources = [e.content for e in session.query(Entry).all()] + [r.text for r in session.query(Reminder).all()]
    for line in lines:
        assert line["kind"] in ("count", "quote"), line
        if line["kind"] == "quote":
            assert line["text"] == f"“{line['quote']}”"
            assert any(line["quote"] in source for source in sources), line
        else:
            assert sorted(_numbers(line["text"])) == sorted(line["counts"]), line


def test_the_counts_are_the_rows(session):
    _notebook(session)
    by_part = {}
    for line in day_digest.compose(session, NOW)["lines"]:
        by_part.setdefault(line["part"], []).append(line)
    assert by_part["due"][0]["text"] == "One reminder due today and one overdue."
    assert by_part["due"][0]["counts"] == [1, 1]
    assert [q["quote"] for q in by_part["due"][1:]] == ["Renew the boat licence", "Call Sam about the deposit"]
    assert by_part["questions"][0]["text"] == "One question in your notes is still open."
    assert by_part["questions"][1]["quote"] == "Should we book the boat for May?"
    assert by_part["changed"][0]["text"] == "One note written and one note edited since this time yesterday."
    assert by_part["quiet"][0]["text"].startswith("Fitness: no new note in 45 days")


def test_an_empty_day_says_so(session):
    got = day_digest.compose(session, NOW)
    assert got["lines"] == [] and got["empty"]


def test_the_route_serves_it_signed_in(client):
    token = client.post("/auth/setup", json={"password": "first-pass"}).json()["token"]
    got = client.get("/insights/day", params={"now": "2026-10-10T14:00:00+00:00"}, headers={"X-Auth-Token": token})
    assert got.status_code == 200
    assert "lines" in got.json()


def test_the_dashboard_draws_the_day_with_no_model():
    js = with_pieces("dashboard.js")
    assert '"/insights/day"' in js


def test_a_quote_skips_a_frontmatter_block_and_a_line_with_no_words() -> None:
    # Audit 1031 Z16: a note that opens with frontmatter was quoted as "---".
    meeting = "---\ntype: meeting\ndate: 2026-10-10\n---\n\n# Harbor sync\nBoat for May."
    assert day_digest._first_line(meeting) == "Harbor sync"
    assert day_digest._first_line("---\n\n***\nPlain words here") == "Plain words here"
    assert day_digest._first_line("---\ntitle: never closed\nbody") == "title: never closed"
    assert day_digest._first_line("# Title only") == "Title only"
    assert day_digest._first_line("---\n---\n") == ""
