"""Open questions (WORLD_CLASS_PLAN I3, H2; row 7).

Every question a note asks in passing is a `derived_facts` row of kind
`question` (the night pass, `ai/facts.py`). This module says what state each
one is in and lets the person change it:

- **answered**, when a later note answers it: either the night pass found
  the answer (an `answered` row whose payload names this question, pass 5),
  or the person marked it by hand and named the note;
- **dropped**, when the person says it no longer matters;
- **open** otherwise.

**The state lives on the question's own payload and on the pass's rows, no
new table** (I3's "Data": "payload `{answered_by, dropped}`; no new table").
An answer the pass found stays an `answered` row with its own provenance
(which model, when, the sentence); reopening such a question tombstones that
row, the same "dismiss, and never work this out again" every derived fact
has, so the pass does not hand the same answer back next night.

**The answered-by link** (I3, decided 2026-10-04; HISTORY, "row 7"): the view links
each answered question to the sentence that answers it, in its note. A typed
link between the two notes (`context`, "answers: ...") is written only when
the person marks a question answered by hand: the night pass never writes to
the graph unasked, as it never writes to a note (I1).
"""

from __future__ import annotations

import re

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from tessellate.ai import facts, learning
from tessellate.ai.composer_frame import note_title
from tessellate.core.database import DerivedFact, Entry, utcnow

STATES = ("open", "answered", "dropped")

#: The most notes an Ask scoped to the open questions reads: the newest
#: notes that still hold one. `ChatRequest.note_ids` takes twenty.
ASK_SCOPE_NOTES = 20


def _payload(row: DerivedFact) -> dict[str, Any]:
    try:
        value = json.loads(row.payload or "{}")
    except ValueError:
        return {}
    return value if isinstance(value, dict) else {}


def _answers_by_question(session: Session, question_ids: list[int] | None = None) -> dict[int, DerivedFact]:
    """The live `answered` row for each question that has one, newest first."""
    rows = session.scalars(
        facts._visible(select(DerivedFact))
        .where(DerivedFact.kind == "answered")
        .order_by(DerivedFact.id.desc())
    ).all()
    found: dict[int, DerivedFact] = {}
    for row in rows:
        other = _payload(row).get("other_fact_id")
        if isinstance(other, int) and other not in found and (question_ids is None or other in question_ids):
            found[other] = row
    return found


def state_of(question: DerivedFact, answer: DerivedFact | None) -> str:
    payload = _payload(question)
    if payload.get("dropped"):
        return "dropped"
    if answer is not None or payload.get("answered_by_entry"):
        return "answered"
    return "open"


def _plain(text: str) -> str:
    """Text as a row shows it: no list marker, no `**` or `__` (INBOX 745
    (b): "strip markdown from the question and from the note title shown").
    The stored text keeps them, being the note's span exactly."""
    text = re.sub(r"^\s*(?:[-*+]|\d+[.)])\s+", "", text or "")
    return re.sub(r"(\*\*|__)", "", text).strip()


def _as_json(question: DerivedFact, answer: DerivedFact | None, notes: dict[int, Entry]) -> dict:
    payload = _payload(question)
    note = notes.get(question.entry_id)
    out = {
        "id": question.id,
        "entry_id": question.entry_id,
        "text": question.text,
        "display": _plain(question.text),
        "span": [question.span_start, question.span_end],
        "asked_at": note.created_at.isoformat() if note is not None and note.created_at else None,
        "note_title": note_title(note.content, size=60) if note is not None else "",
        "state": state_of(question, answer),
        "answered_by": None,
    }
    if answer is not None:
        by = notes.get(answer.entry_id)
        out["answered_by"] = {
            "fact_id": answer.id,
            "entry_id": answer.entry_id,
            "text": answer.text,
            "span": [answer.span_start, answer.span_end],
            "at": by.created_at.isoformat() if by is not None and by.created_at else None,
            "note_title": note_title(by.content, size=60) if by is not None else "",
            "model": answer.model,
            "reason": _payload(answer).get("reason") or "",
            "by_hand": False,
        }
    elif payload.get("answered_by_entry"):
        by = notes.get(int(payload["answered_by_entry"]))
        out["answered_by"] = {
            "fact_id": None,
            "entry_id": int(payload["answered_by_entry"]),
            "text": "",
            "span": None,
            "at": payload.get("answered_at"),
            "note_title": note_title(by.content, size=60) if by is not None else "",
            "model": "you",
            "reason": "",
            "by_hand": True,
        }
    return out


def open_counts(session: Session, entry_ids: list[int]) -> dict[str, int]:
    """Open questions per note, for the notes asked about that have any
    (INBOX 745 (c): a card says "2 open questions")."""
    if not entry_ids:
        return {}
    facts._retire_not_own_questions(session)
    rows = list(session.scalars(
        facts._visible(select(DerivedFact))
        .where(DerivedFact.kind == "question", DerivedFact.entry_id.in_(entry_ids))
    ).all())
    answers = _answers_by_question(session, [row.id for row in rows]) if rows else {}
    counts: dict[str, int] = {}
    for row in rows:
        if state_of(row, answers.get(row.id)) == "open":
            counts[str(row.entry_id)] = counts.get(str(row.entry_id), 0) + 1
    return counts


def _notes_for(session: Session, page: list) -> dict[int, Entry]:
    """The notes a page of questions names: their own, their answers', and any answered by hand."""
    wanted = {row.entry_id for row, _a, _s in page}
    wanted |= {answer.entry_id for _r, answer, _s in page if answer is not None}
    for row, _a, _s in page:
        by_hand = _payload(row).get("answered_by_entry")
        if by_hand:
            wanted.add(int(by_hand))
    if not wanted:
        return {}
    return {entry.id: entry for entry in session.scalars(select(Entry).where(Entry.id.in_(wanted))).all()}


def listing(
    session: Session, *, state: str | None = None, limit: int = 50, offset: int = 0, entry_id: int | None = None
) -> dict:
    """One page of questions in `state` (all when None), newest note first,
    with the count in each state.

    The state is worked out per row rather than stored, so the page is cut in
    Python after the states are known. Measured against the gate (500
    questions under 100 ms) by `tests/test_questions_view.py`.
    """
    #: Rows an older rule stored (a quoted prompt, a piece of one cut at its
    #: closing quote) leave the list now, not at the next night pass: that
    #: pass runs only with background tasks on, and the list kept showing
    #: `" or "What's the most ...` hours after the rule was fixed (INBOX 785).
    facts._retire_not_own_questions(session)
    questions = list(
        session.scalars(
            facts._visible(select(DerivedFact))
            .where(DerivedFact.kind == "question")
            .where(DerivedFact.entry_id == entry_id if entry_id is not None else True)
            .order_by(DerivedFact.entry_id.desc(), DerivedFact.span_start, DerivedFact.id)
        ).all()
    )
    answers = _answers_by_question(session)
    states = [(row, answers.get(row.id), state_of(row, answers.get(row.id))) for row in questions]
    counts = {name: 0 for name in STATES}
    for _row, _answer, name in states:
        counts[name] += 1
    chosen = [item for item in states if state is None or item[2] == state]
    page = chosen[offset : offset + limit]
    notes = _notes_for(session, page)
    return {
        "items": [_as_json(row, answer, notes) for row, answer, _s in page],
        "total": len(chosen),
        "counts": counts,
    }


def summary(session: Session) -> dict:
    """The Dashboard's line: how many are open, and the oldest open one."""
    page = listing(session, state="open", limit=10_000)
    items = page["items"]
    oldest = min(items, key=lambda item: (item["asked_at"] or "", item["id"])) if items else None
    return {"open": page["counts"]["open"], "oldest": oldest}


def visible_question(session: Session, fact_id: int) -> DerivedFact | None:
    row = facts.visible(session, fact_id)
    return row if row is not None and row.kind == "question" else None


def set_state(session: Session, question: DerivedFact, state: str, entry_id: int | None = None) -> dict:
    """Move a question to `state`. Every move is a correction (I7).

    - `dropped`: kept, with `dropped` on its payload; reversible.
    - `open`: clears dropped and a by-hand answer, and tombstones the pass's
      answer, so the next night does not answer it again with the same note.
    - `answered`: by hand, `entry_id` names the note that answers it; a
      `context` link from that note to the question's is written.
    """
    if state not in STATES:
        raise ValueError(f"state must be one of {', '.join(STATES)}")
    payload = _payload(question)
    if state == "dropped":
        payload["dropped"] = True
        learning.record(session, kind="drop_question", subject={"fact_id": question.id}, excerpt=question.text[:200])
    elif state == "open":
        payload.pop("dropped", None)
        payload.pop("answered_by_entry", None)
        payload.pop("answered_at", None)
        answer = _answers_by_question(session, [question.id]).get(question.id)
        if answer is not None:
            facts.remove(session, answer)
        learning.record(session, kind="reopen_question", subject={"fact_id": question.id}, excerpt=question.text[:200])
    else:
        if entry_id is None:
            raise ValueError("say which note answers it")
        answering = session.get(Entry, entry_id)
        if answering is None or answering.is_deleted or answering.is_private:
            raise LookupError("That note could not be found.")
        if answering.id == question.entry_id:
            raise ValueError("a question cannot be answered by its own note")
        payload.pop("dropped", None)
        payload["answered_by_entry"] = answering.id
        payload["answered_at"] = utcnow().isoformat()
        asked_in = session.get(Entry, question.entry_id)
        if asked_in is not None:
            from tessellate.entry import manager_links

            manager_links.create_link(
                session,
                answering,
                asked_in,
                reason=f"answers: {question.text[:150]}",
                link_type="context",
            )
        learning.record(
            session, kind="answer_question", subject={"fact_id": question.id, "entry_id": answering.id},
            excerpt=question.text[:200],
        )
    question.payload = json.dumps(payload) if payload else None
    session.flush()
    answer = _answers_by_question(session, [question.id]).get(question.id)
    wanted = {question.entry_id} | ({answer.entry_id} if answer is not None else set())
    if payload.get("answered_by_entry"):
        wanted.add(int(payload["answered_by_entry"]))
    notes = {entry.id: entry for entry in session.scalars(select(Entry).where(Entry.id.in_(wanted))).all()}
    return _as_json(question, answer, notes)


def open_note_ids(session: Session, limit: int = ASK_SCOPE_NOTES) -> list[int]:
    """The newest notes that still hold an unanswered question, for the Ask scope."""
    ids: list[int] = []
    for item in listing(session, state="open", limit=10_000)["items"]:
        if item["entry_id"] not in ids:
            ids.append(item["entry_id"])
        if len(ids) >= limit:
            break
    return ids

