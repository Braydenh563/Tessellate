"""Reads and writes for "Check what it learned" (CHAT_PLAN decision 68).

`ai/learned_audit.check` decides; this module loads the open rows and their
notes, writes the decisions, and takes them back.

A decision is written on the row itself, in `DerivedFact.payload` under
`audit` (a pair row's payload keeps its other keys): the action, the code and
words of the reason, and the run's stamp. A retirement is a tombstone, the
same `facts.remove` the row's Delete uses, so the night shift does not learn
the sentence again; it is not a correction, because the person did not say
it was wrong. A flag changes nothing but the mark.

**Undo is by stamp.** `undo(stamp)` lifts the tombstones that stamp wrote and
marks each `restored`, so a later check leaves the row alone: the person's
word beats the rule's. A row that was deleted by the person after a check
is not lifted.
"""

from __future__ import annotations

import json
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from tessellate.ai import facts, verdicts
from tessellate.ai.facts import entry_tags
from tessellate.ai.learned_audit import RETIRE, FactView, Finding, NoteView, check
from tessellate.core import clock
from tessellate.core.database import DerivedFact, Entry, utcnow

#: Most lines a run says about what it retired, so a thousand rows do not
#: push everything else out of the ledger's fifty.
LINES_SAID = 12


def _payload(row: DerivedFact) -> dict:
    try:
        data = json.loads(row.payload or "{}")
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def _mark(row: DerivedFact) -> dict:
    return _payload(row).get("audit") or {}


def _view(row: DerivedFact) -> FactView:
    data = _payload(row)
    sides = tuple(int(data[key]) for key in ("fact_id", "other_fact_id") if isinstance(data.get(key), int))
    return FactView(
        id=row.id, entry_id=row.entry_id, kind=row.kind, text=row.text, span=(row.span_start, row.span_end),
        edited=bool(row.edited_by_user), written=row.computed_at, sides=sides,
    )


def load(session: Session) -> tuple[list[FactView], dict[int, NoteView]]:
    """The open rows the check judges and the notes they came from. A row the
    person has put back after a check (`audit.restored`) is left out; a
    private note's rows are never read (its text is ciphertext)."""
    pairs = session.execute(
        select(DerivedFact, Entry)
        .join(Entry, Entry.id == DerivedFact.entry_id)
        .where(DerivedFact.deleted_at.is_(None), DerivedFact.kind.in_(facts.JUDGED_KINDS), Entry.is_private.is_(False))
    ).all()
    rows, notes = [], {}
    for fact, entry in pairs:
        if _mark(fact).get("restored"):
            continue
        rows.append(_view(fact))
        notes[entry.id] = NoteView(
            id=entry.id, content=entry.content or "", tags=entry_tags(entry), written=entry.created_at, gone=bool(entry.is_deleted)
        )
    return rows, notes


def _write(row: DerivedFact, finding: Finding | None, stamp: str) -> None:
    data = _payload(row)
    if finding is None:
        if "audit" not in data:
            return
        data.pop("audit")
    else:
        data["audit"] = {
            "action": finding.action, "code": finding.code, "reason": finding.reason,
            "detail": finding.detail, "run": stamp,
        }
    row.payload = json.dumps(data) if data else None


def apply(session: Session, findings: list[Finding], stamp: str, at: datetime | None = None) -> dict:
    """Write the findings: retire or flag each row, and clear a flag an
    earlier check wrote that no longer holds. Returns the ids by action."""
    by_id = {item.fact_id: item for item in findings}
    done: dict[str, list[int]] = {"retired": [], "flagged": []}
    for row in session.scalars(select(DerivedFact).where(DerivedFact.kind.in_(facts.JUDGED_KINDS), DerivedFact.deleted_at.is_(None))):
        found = by_id.get(row.id)
        if _mark(row).get("restored") or (found is None and _mark(row).get("action") != "flag"):
            continue
        _write(row, found, stamp)
        if found is not None and found.action == RETIRE:
            facts.remove(session, row, at)
            done["retired"].append(row.id)
        elif found is not None:
            done["flagged"].append(row.id)
    session.flush()
    return done


def run_check(session: Session, today: date | None = None, now: datetime | None = None) -> dict:
    """The whole pass: load, judge, write. The caller commits."""
    rows, notes = load(session)
    findings = check(rows, notes, verdicts.known(session), today or clock.today())
    stamp = (now or utcnow()).isoformat(timespec="seconds")
    done = apply(session, findings, stamp, now)
    texts = {fact.id: fact.text for fact in rows}
    return {
        "run": stamp, "checked": len(rows), **done,
        "lines": [
            {"id": item.fact_id, "action": item.action, "code": item.code, "reason": item.reason, "text": texts.get(item.fact_id, "")}
            for item in findings
        ],
    }


def summary_words(done: dict) -> str:
    """One line for a run's result and the panel."""
    retired, flagged, checked = len(done["retired"]), len(done["flagged"]), done["checked"]
    if not (retired or flagged):
        return f"checked {checked} thing{'' if checked == 1 else 's'}, all of them still hold"
    parts = [f"retired {retired}" if retired else "", f"flagged {flagged}" if flagged else ""]
    return f"checked {checked}, " + " and ".join(part for part in parts if part)


def say_lines(run, done: dict) -> None:  # noqa: ANN001  # a jobruns.Run
    """The ledger's lines for a run: what went and why, then the count."""
    for item in done["lines"][:LINES_SAID]:
        verb = "Retired" if item["action"] == RETIRE else "Flagged"
        text = " ".join(item["text"].split())
        run.say(f"{verb} “{text[:60]}{'...' if len(text) > 60 else ''}”: {item['reason']}")
    if len(done["lines"]) > LINES_SAID:
        run.say(f"And {len(done['lines']) - LINES_SAID} more.")


def last_run(session: Session) -> dict:
    """What the latest check did and what is still undoable, from the rows' own
    marks: `{"run": stamp, "retired": [...], "flagged": [...]}`; run None before any."""
    marked = []
    for row in session.scalars(select(DerivedFact).where(DerivedFact.payload.is_not(None))):
        mark = _mark(row)
        if mark.get("run") and not mark.get("restored"):
            marked.append((row, mark))
    stamp = max((mark["run"] for _row, mark in marked), default=None)
    out: dict = {"run": stamp, "retired": [], "flagged": []}
    for row, mark in marked:
        item = {"id": row.id, "entry_id": row.entry_id, "kind": row.kind, "text": row.text, "reason": mark.get("reason", ""), "run": mark["run"]}
        if mark.get("action") == RETIRE and row.deleted_at is not None and mark["run"] == stamp:
            out["retired"].append(item)
        elif mark.get("action") == "flag" and row.deleted_at is None:
            out["flagged"].append(item)
    return out


def flags(session: Session) -> dict[int, str]:
    """fact id -> the words of its open flag, for the list to show."""
    out = {}
    for row in session.scalars(select(DerivedFact).where(DerivedFact.payload.is_not(None), DerivedFact.deleted_at.is_(None))):
        mark = _mark(row)
        if mark.get("action") == "flag" and not mark.get("restored"):
            out[row.id] = mark.get("reason", "")
    return out


def keep(session: Session, fact_id: int) -> bool:
    """Keep it, on one flag (L584): the person's word that the row stands, so
    the flag goes and no later check flags it again. The same `restored` mark
    Undo writes, so the checks already leave it be. False when the row is not
    an open flag."""
    row = session.get(DerivedFact, fact_id)
    if row is None or row.deleted_at is not None:
        return False
    mark = _mark(row)
    if mark.get("action") != "flag" or mark.get("restored"):
        return False
    data = _payload(row)
    data["audit"] = {**mark, "restored": True}
    row.payload = json.dumps(data)
    session.flush()
    return True


def unkeep(session: Session, fact_id: int) -> bool:
    """Undo of `keep`: the flag is raised again. Only a kept flag, never the
    `restored` mark an undone retirement carries."""
    row = session.get(DerivedFact, fact_id)
    if row is None or row.deleted_at is not None:
        return False
    mark = _mark(row)
    if mark.get("action") != "flag" or not mark.get("restored"):
        return False
    data = _payload(row)
    data["audit"] = {key: value for key, value in mark.items() if key != "restored"}
    row.payload = json.dumps(data)
    session.flush()
    return True


def undo(session: Session, stamp: str) -> int:
    """Put back what the check at `stamp` retired. Each row is marked restored,
    so the next check leaves it be. Rows the person deleted since are not lifted."""
    lifted = 0
    for row in session.scalars(select(DerivedFact).where(DerivedFact.payload.is_not(None), DerivedFact.deleted_at.is_not(None))):
        mark = _mark(row)
        if mark.get("run") != stamp or mark.get("action") != RETIRE or mark.get("restored"):
            continue
        data = _payload(row)
        data["audit"] = {**mark, "restored": True}
        row.payload = json.dumps(data)
        facts.restore(session, row)
        lifted += 1
    session.flush()
    return lifted



def redo(session: Session, stamp: str, at: datetime | None = None) -> int:
    """Redo of `undo`: retire again what the check at `stamp` retired and the
    person put back, and take the `restored` mark off so it is the check's again."""
    taken = 0
    for row in session.scalars(select(DerivedFact).where(DerivedFact.payload.is_not(None), DerivedFact.deleted_at.is_(None))):
        mark = _mark(row)
        if mark.get("run") != stamp or mark.get("action") != RETIRE or not mark.get("restored"):
            continue
        data = _payload(row)
        data["audit"] = {key: value for key, value in mark.items() if key != "restored"}
        row.payload = json.dumps(data)
        facts.remove(session, row, at)
        taken += 1
    session.flush()
    return taken


def run_job() -> None:
    """The scheduled job and Run now's: its own session, one `jobruns` run
    with the lines of what went and why."""
    from tessellate.core import deps, jobruns

    session = deps.get_db().session()
    try:
        with jobruns.job_run("learned-audit") as run:
            run.say("Re-reading what it learned against its notes.")
            done = run_check(session)
            session.commit()
            say_lines(run, done)
            run.result = summary_words(done)
    finally:
        session.close()
