"""Time travel over meaning (WORLD_CLASS_PLAN I5, H8, row 23): a question
answered from the notebook as it stood on a date, and a note's claims then
against now. `ai/timetravel.py` holds the reasoning; these are the spec's
"tests first", written from its own list:

* a note edited on three dates answers differently as of each date, citing
  the right revision;
* the then-and-now diff on the fixture reports one revised, one dropped, one
  new;
* an `as_of` before the notebook existed returns an empty, honest answer
  rather than today's;
* the gate: as-of retrieval under 1 s for a 200-candidate set.
"""

from __future__ import annotations

import json
import time
from datetime import date, datetime, timedelta, timezone

from tessellate.ai import timetravel
from tessellate.core.database import EntryRevision
from tessellate.entry import manager

T0 = datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc)


def _note_with_history(session, texts: list[str], days: list[int]):
    """A note whose text was `texts[0]` from day `days[0]`, `texts[1]` from
    day `days[1]` and so on, the last being its text now. Revisions hold the
    text *before* an edit, stamped at the edit, as `record_revision` does."""
    entry = manager.create_entry(session, texts[-1], "Work", [])
    entry.created_at = T0 + timedelta(days=days[0])
    for before, edited_on in zip(texts[:-1], days[1:]):
        session.add(EntryRevision(entry_id=entry.id, content=before, tags="[]", created_at=T0 + timedelta(days=edited_on)))
    session.commit()
    return entry


BATCH = [
    "The batch size should stay at 32.",
    "The batch size goes to 48 after the profiler run.",
    "The batch size is 64 after the memory fix.",
]


def test_the_text_as_of_each_date_is_the_version_that_stood_then(session):
    entry = _note_with_history(session, BATCH, [0, 30, 60])
    for day, want in ((10, BATCH[0]), (45, BATCH[1]), (90, BATCH[2])):
        then = timetravel.text_as_of(session, entry, T0 + timedelta(days=day))
        assert then is not None and then.text == want, (day, then)
    assert timetravel.text_as_of(session, entry, T0 - timedelta(days=1)) is None
    first = timetravel.text_as_of(session, entry, T0 + timedelta(days=10))
    assert first.revision_id is not None and first.exact


def test_a_question_as_of_a_date_is_answered_from_that_version(ai_client, fake_ollama, session):
    entry = _note_with_history(session, BATCH, [0, 30, 60])
    fake_ollama.librarian_reply = "It was 48 then."
    seen = []
    real = fake_ollama.chat_stream

    def spy(model, messages, *args, **kwargs):
        seen.append(json.dumps(messages))
        return real(model, messages, *args, **kwargs)

    fake_ollama.chat_stream = spy
    as_of = (T0 + timedelta(days=45)).date().isoformat()
    with ai_client.stream("POST", "/chat/stream", json={"question": "what batch size?", "as_of": as_of, "use_tools": True}) as r:
        events = [json.loads(line) for line in r.iter_lines() if line]
    meta = next(e for e in events if e["type"] == "meta")
    assert meta["as_of"] == as_of
    record = next(row for row in meta["raw_results"] if row["id"] == entry.id)
    assert record["content"] == BATCH[1]
    assert meta["as_of_revisions"][str(entry.id)] is not None
    assert seen and BATCH[1] in seen[-1] and BATCH[2] not in seen[-1]
    # The present cannot leak in through a tool: an as-of turn reads, it does
    # not act, so it runs without tools.
    assert not [e for e in events if e["type"] == "tool"]


def test_before_the_notebook_existed_the_answer_is_empty_and_says_so(ai_client, fake_ollama, session):
    _note_with_history(session, BATCH, [0, 30, 60])
    with ai_client.stream("POST", "/chat/stream", json={"question": "what batch size?", "as_of": "2025-01-01"}) as r:
        events = [json.loads(line) for line in r.iter_lines() if line]
    meta = next(e for e in events if e["type"] == "meta")
    assert meta["raw_results"] == []
    answer = "".join(e.get("delta", "") for e in events if e["type"] == "answer")
    assert "1 January 2025" in answer and "no notes" in answer.lower()


def test_the_unstreamed_chat_takes_as_of_too(ai_client, fake_ollama, session):
    entry = _note_with_history(session, BATCH, [0, 30, 60])
    as_of = (T0 + timedelta(days=45)).date().isoformat()
    body = ai_client.post("/chat", json={"question": "what batch size?", "as_of": as_of}).json()
    record = next(row for row in body["raw_results"] if row["id"] == entry.id)
    assert record["content"] == BATCH[1]


def test_then_and_now_reports_one_revised_one_dropped_one_new(ai_client, session):
    then = (
        "The batch size should stay at 32. We train on the March dataset only. "
        "Evaluation runs every night."
    )
    now = (
        "The batch size is 64 after the memory fix. Evaluation runs every night. "
        "We add a warmup of 500 steps."
    )
    entry = _note_with_history(session, [then, now], [0, 30])
    body = ai_client.get(f"/entries/{entry.id}/then-and-now", params={"as_of": (T0 + timedelta(days=10)).date().isoformat()}).json()
    kinds = sorted(change["kind"] for change in body["changed"])
    assert kinds == ["dropped", "new", "revised"], body
    revised = next(c for c in body["changed"] if c["kind"] == "revised")
    assert "32" in body["then"][revised["then"]] and "64" in body["now"][revised["now"]]
    assert body["revision_id"] is not None


def test_a_history_row_is_compared_by_its_own_text(ai_client, session):
    """History's "Then and now" sends the row's version: two edits on one day
    are still two versions, which a day cannot tell apart."""
    entry = _note_with_history(session, ["The batch size should stay at 32.", "The batch size is 64 after the memory fix."], [0, 30])
    body = ai_client.post(f"/entries/{entry.id}/then-and-now", json={"then": "The batch size should stay at 32."}).json()
    assert [c["kind"] for c in body["changed"]] == ["revised"]


def test_then_and_now_before_the_note_existed_is_a_404_that_says_why(ai_client, session):
    entry = _note_with_history(session, BATCH, [0, 30, 60])
    response = ai_client.get(f"/entries/{entry.id}/then-and-now", params={"as_of": "2025-01-01"})
    assert response.status_code == 404
    assert "did not exist" in response.json()["detail"]


def test_the_gate_as_of_retrieval_over_200_candidates_is_under_a_second(session):
    entries = []
    for index in range(200):
        entries.append(
            _note_with_history(
                session,
                [f"note {index} about the reactor schedule, draft {k}" for k in range(4)],
                [0, 20, 40, 60],
            )
        )
    started = time.process_time()
    picked = timetravel.rewind(session, "reactor schedule draft", T0 + timedelta(days=30), entries, limit=5)
    elapsed = time.process_time() - started
    assert len(picked) == 5 and all(p.text.endswith("draft 1") for p in picked)
    assert elapsed < 1.0, f"{elapsed:.3f}s"


def test_a_window_too_old_for_the_kept_history_is_marked_not_exact(session):
    entry = manager.create_entry(session, "v21", "Work", [])
    entry.created_at = T0
    for k in range(manager.MAX_REVISIONS):
        session.add(EntryRevision(entry_id=entry.id, content=f"v{k + 1}", tags="[]", created_at=T0 + timedelta(days=10 + k)))
    session.commit()
    early = timetravel.text_as_of(session, entry, T0 + timedelta(days=5))
    assert early.text == "v1" and not early.exact
    assert date(2026, 3, 1) == T0.date()
