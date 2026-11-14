"""L-timeline-2: a span brushed on the timeline strip, said as a review.

`/timeline/digest?start=&end=` answers with the composed review of the notes
written in those days (`composer_voice.span_review`, the week's writer with
the span's own ends, no model) and the notes themselves, oldest first, so the
sheet can list them beside what it says.

Fixed clock: Tuesday 10 November 2026, 09:00."""

from __future__ import annotations

import datetime as dt

import pytest

from tessellate.core import config
from tessellate.entry import manager

NOW = dt.datetime(2026, 11, 10, 9, 0, 0)


@pytest.fixture
def book(client, session, monkeypatch):
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    notes = [
        ("# Harbor launch plan\n\nShip the mobile app to the public on the 14th.", dt.datetime(2026, 10, 3, 10), "Work"),
        ("# Lisbon trip\n\nThe tram to Belem leaves from Praca da Figueira.", dt.datetime(2026, 10, 20, 18), "Travel"),
        ("Garden shed roof leaks in the north corner after the rain.", dt.datetime(2026, 11, 9, 10), "Home"),
        ("# September budget\n\nRent went up by forty.", dt.datetime(2026, 9, 28, 9), "Home"),
    ]
    for text, when, category in notes:
        entry = manager.create_entry(session, text, category)
        entry.created_at = entry.updated_at = when
    session.commit()
    return session


def test_the_span_names_its_notes_and_its_ends(client, book):
    got = client.get("/timeline/digest", params={"start": "2026-10-01", "end": "2026-10-31"})
    assert got.status_code == 200
    body = got.json()
    assert [n["title"] for n in body["notes"]] == ["Harbor launch plan", "Lisbon trip"]
    assert [n["day"] for n in body["notes"]] == ["2026-10-03", "2026-10-20"]
    assert body["text"].startswith("You wrote two notes from ")
    assert "Lisbon trip" in body["text"] and "Garden shed" not in body["text"]
    assert "last seven days" not in body["text"]
    assert body["composed"] is True


def test_an_empty_span_says_so(client, book):
    body = client.get("/timeline/digest", params={"start": "2026-08-01", "end": "2026-08-31"}).json()
    assert body["notes"] == []
    assert body["text"] == "Nothing was written in these days."


@pytest.mark.parametrize(
    "params",
    [
        {"start": "2026-10-31", "end": "2026-10-01"},
        {"start": "2026-10-01", "end": "not-a-day"},
        {"start": "2020-01-01", "end": "2026-10-01"},
    ],
)
def test_a_backwards_bad_or_huge_span_is_refused(client, book, params):
    assert client.get("/timeline/digest", params=params).status_code == 422


# The strip side: Shift and a drag on the density strip brushes the days.

import json  # noqa: E402
import os  # noqa: E402
import re  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402

from tests._app_js import JS_DIR  # noqa: E402

TIMELINE = (JS_DIR / "timeline.js").read_text(encoding="utf-8")


def _function(name: str) -> str:
    start = TIMELINE.index(f"function {name}(")
    match = re.search(r"\n}\n", TIMELINE[start:])
    assert match
    return TIMELINE[start : start + match.end()]


def _spans() -> str:
    """`timelineSpans`, the one name the gap lines and the brush share."""
    start = TIMELINE.index("const timelineSpans = {")
    return TIMELINE[start : TIMELINE.index("\n};\n", start) + 4]


def _method(name: str) -> str:
    spans = _spans()
    start = re.search(rf"\n  (?:async )?{name}\(", spans).start()
    return spans[start : spans.index("\n  },", start) + 5]


BRUSH = r"""
const timelineBucketKey = (d) => d.toISOString().slice(0, 10);
%s
const day = 864e5;
const newest = Date.UTC(2026, 10, 10);
const span = { newest, width: 100 * day, oldest: newest - 100 * day };
const box = { top: 100, height: 1000 };
process.stdout.write(JSON.stringify([
  timelineSpans.fromBrush(110, 300, box, span),
  timelineSpans.fromBrush(300, 110, box, span),
  timelineSpans.fromBrush(50, 2000, box, span),
  timelineSpans.fromBrush(200, 202, box, span),
]));
"""


@pytest.mark.skipif(not shutil.which("node"), reason="node is not installed")
def test_a_brush_reads_as_its_days_whichever_way_it_was_drawn():
    out = subprocess.run(["node", "-e", BRUSH % _spans()], capture_output=True, text=True, timeout=30, env={**os.environ, "TZ": "UTC"})
    assert out.returncode == 0, out.stderr
    got = json.loads(out.stdout)
    # 1% to 20% down a 100-day strip: 10 Nov less 20 days to less 1 day.
    assert got[0] == {"start": "2026-10-21", "end": "2026-11-09"}
    assert got[1] == got[0]
    # Past either end is clamped to the strip.
    assert got[2] == {"start": "2026-08-02", "end": "2026-11-10"}
    # A press that hardly moved is a click (the jump), not a brush.
    assert got[3] is None


def test_shift_and_drag_brushes_and_a_plain_drag_still_jumps():
    wiring = TIMELINE[TIMELINE.index('$("timeline-scrubber").addEventListener("pointerdown"') :][:1500]
    assert "event.shiftKey" in wiring
    assert "timelineScrubTo(event.clientY)" in wiring
    assert "timelineSpans.open(" in wiring


def test_the_span_sheet_is_the_sheet_recipe_with_the_notes_beside_the_review():
    body = _method("open")
    assert "/timeline/digest?start=" in body
    for part in ("openSheet(", "renderMarkdown(", "connectionRowEl(", "timeline-span-notes"):
        assert part in body, part


# --- The model path (CHAT_PLAN decision 75: model on and model off agree) ----


def test_with_a_model_the_span_is_said_by_the_model_over_the_spans_notes(book, ai_client, fake_ollama):
    fake_ollama.librarian_reply = "October was the Harbor launch and a Lisbon trip."
    body = ai_client.get("/timeline/digest", params={"start": "2026-10-01", "end": "2026-10-31"}).json()
    assert body["text"] == "October was the Harbor launch and a Lisbon trip." and body["composed"] is False
    prompt = fake_ollama.chat_calls[-1][-1]["content"]
    assert "Harbor launch plan" in prompt and "Lisbon trip" in prompt
    assert "Garden shed" not in prompt and "September budget" not in prompt  # only the span's notes
    assert "from 1 October 2026 to 31 October 2026" in prompt  # the span's own ends
    assert [n["title"] for n in body["notes"]] == ["Harbor launch plan", "Lisbon trip"]


def test_a_failed_model_call_falls_back_to_the_composed_review(book, ai_client, fake_ollama, monkeypatch):
    from tessellate.ai.ollama_client import OllamaError

    def broken(*_a, **_k):
        raise OllamaError("timed out")

    monkeypatch.setattr(fake_ollama, "chat", broken)
    body = ai_client.get("/timeline/digest", params={"start": "2026-10-01", "end": "2026-10-31"}).json()
    assert body["composed"] is True and body["text"].startswith("You wrote two notes from ")


def test_a_stopped_model_falls_back_to_the_composed_review(book, ai_client, fake_ollama):
    fake_ollama.running = False
    body = ai_client.get("/timeline/digest", params={"start": "2026-10-01", "end": "2026-10-31"}).json()
    assert body["composed"] is True and body["text"].startswith("You wrote two notes from ")
    assert not fake_ollama.chat_calls


def test_an_empty_span_never_asks_the_model(book, ai_client, fake_ollama):
    ai_client.get("/timeline/digest", params={"start": "2026-08-01", "end": "2026-08-31"})
    assert not fake_ollama.chat_calls


def test_a_slow_model_is_not_waited_for(book, ai_client, fake_ollama, monkeypatch):
    """The model call runs inside the GET the sheet waits on: past
    SPAN_MODEL_TIMEOUT the composed review is served instead."""
    import threading

    from tessellate.api import routes_timeline

    release = threading.Event()

    def slow(*_a, **_k):
        release.wait(5)
        return {"content": "Too late.", "thinking": ""}

    monkeypatch.setattr(routes_timeline, "SPAN_MODEL_TIMEOUT", 0.05)
    monkeypatch.setattr(fake_ollama, "chat", slow)
    try:
        body = ai_client.get("/timeline/digest", params={"start": "2026-10-01", "end": "2026-10-31"}).json()
    finally:
        release.set()
    assert body["composed"] is True and body["text"].startswith("You wrote two notes from ")


def test_the_span_reads_only_its_own_days_from_the_database(book, monkeypatch):
    """Both ends are in SQL (with a day's slack for the zone): a span in
    October does not pull November's or September's notes off disk."""
    from tessellate.ai import review_digest

    fetched: list[int] = []
    execute = book.execute

    def counting(statement, *a, **k):
        result = execute(statement, *a, **k)
        rows = result.all()
        fetched.append(len(rows))

        class _Rows:
            def all(self):
                return rows

        return _Rows()

    monkeypatch.setattr(book, "execute", counting)
    notes = review_digest._notes(book, dt.date(2026, 10, 1), dt.timezone.utc, dt.date(2026, 10, 31))
    assert [n["content"][:9] for n in notes] == ["# Harbor ", "# Lisbon "]
    assert fetched == [2]  # not the 9 November note, nor 28 September's
