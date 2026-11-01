"""Decision 68, slices 2 and 3's server half: the pass over the stored rows,
its job, its undo and its routes. A fixed day throughout."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import select

from tessellate.ai import facts, learned_audit_run as run
from tessellate.core import jobruns
from tessellate.core.database import DerivedFact, Entry
from tessellate.entry import manager

TODAY = date(2026, 11, 1)
JOKE = "I never wash my socks, they clean themselves."
REAL = "I always take the early train to work."


def _note(session, content, tags=()):
    made = manager.create_entry(session, content, tags=list(tags))
    session.commit()
    return made.id


def _learn(session, entry_id, text, kind="claim", **more):
    start = session.get(Entry, entry_id).content.find(text)
    row = DerivedFact(entry_id=entry_id, kind=kind, text=text, span_start=max(start, 0), span_end=max(start, 0) + len(text), **more)
    session.add(row)
    session.commit()
    return row.id


def _seed(session):
    joke = _note(session, JOKE, tags=["joke"])
    real = _note(session, REAL, tags=["work"])
    return _learn(session, joke, JOKE), _learn(session, real, REAL)


def test_a_check_retires_the_joke_and_keeps_the_real_claim(session):
    joke_id, real_id = _seed(session)
    done = run.run_check(session, TODAY, datetime(2026, 11, 1, 9, 0, 0))
    session.commit()
    assert done["retired"] == [joke_id] and done["flagged"] == [] and done["checked"] == 2
    assert done["lines"][0]["reason"] == "The note is tagged joke, so this is not a claim about you."
    assert session.get(DerivedFact, joke_id).deleted_at is not None
    assert session.get(DerivedFact, real_id).deleted_at is None
    assert run.summary_words(done) == "checked 2, retired 1"


def test_a_retired_row_is_not_learned_again_by_the_night_shift(session):
    _seed(session)
    run.run_check(session, TODAY)
    session.commit()
    facts.run(session, force=True)
    session.commit()
    again = session.scalars(select(DerivedFact).where(DerivedFact.text == JOKE, DerivedFact.deleted_at.is_(None))).all()
    assert again == []


def test_undo_by_stamp_restores_and_the_next_check_leaves_it_alone(session):
    joke_id, _ = _seed(session)
    done = run.run_check(session, TODAY, datetime(2026, 11, 1, 9, 0, 0))
    session.commit()
    assert [item["id"] for item in run.last_run(session)["retired"]] == [joke_id]
    assert run.undo(session, done["run"]) == 1
    session.commit()
    assert session.get(DerivedFact, joke_id).deleted_at is None
    assert run.last_run(session)["retired"] == []
    again = run.run_check(session, TODAY, datetime(2026, 11, 2, 9, 0, 0))
    assert again["retired"] == [] and again["checked"] == 1
    assert run.undo(session, done["run"]) == 0
    assert run.redo(session, done["run"]) == 1
    session.commit()
    assert session.get(DerivedFact, joke_id).deleted_at is not None
    assert [item["id"] for item in run.last_run(session)["retired"]] == [joke_id]
    assert run.redo(session, done["run"]) == 0


def test_a_row_the_person_deleted_after_a_check_is_not_lifted(session):
    joke_id, _ = _seed(session)
    done = run.run_check(session, TODAY, datetime(2026, 11, 1, 9, 0, 0))
    row = session.get(DerivedFact, joke_id)
    row.payload = None  # as a row the check never touched
    session.commit()
    assert run.undo(session, done["run"]) == 0


def test_a_flag_is_marked_listed_and_cleared_when_it_no_longer_holds(session):
    note = _note(session, "The passport renewal is due on 3 March 2026 at the office.")
    fid = _learn(session, note, "The passport renewal is due on 3 March 2026 at the office.")
    done = run.run_check(session, TODAY)
    session.commit()
    assert done["flagged"] == [fid] and done["retired"] == []
    assert "3 March 2026" in run.flags(session)[fid]
    assert [item["id"] for item in run.last_run(session)["flagged"]] == [fid]
    assert run.summary_words(done) == "checked 1, flagged 1"
    done = run.run_check(session, date(2026, 2, 1))
    session.commit()
    assert done["flagged"] == [] and run.flags(session) == {}


def test_a_pair_payload_keeps_its_keys_beside_the_mark(session):
    note = _note(session, "x is not here. " + REAL)
    gone = _note(session, "nothing relevant")
    claim = _learn(session, note, REAL)
    ghost = _learn(session, gone, "A sentence the note never held at all.")
    pair = _learn(
        session, note, REAL, kind="tension",
        payload='{"pair": "tension:1:2", "fact_id": %d, "other_fact_id": %d, "reason": "r"}' % (claim, ghost),
    )
    done = run.run_check(session, TODAY)
    session.commit()
    assert set(done["retired"]) == {ghost, pair}
    import json

    stored = json.loads(session.get(DerivedFact, pair).payload)
    assert stored["pair"] == "tension:1:2" and stored["audit"]["code"] == "pair-side-gone"


def test_private_and_binned_notes(session):
    gone = _note(session, "A claim that I always do. " + REAL)
    fid = _learn(session, gone, REAL)
    session.get(Entry, gone).is_deleted = True
    session.commit()
    done = run.run_check(session, TODAY)
    assert done["retired"] == [fid] and done["lines"][0]["code"] == "note-gone"


def test_the_route_runs_a_job_with_lines_and_undoes_it(client, session):
    joke_id, real_id = _seed(session)
    out = client.post("/learned/audit/run").json()
    assert out["retired"] == [joke_id] and out["summary"].startswith("checked 2, retired 1")
    ran = {item["kind"]: item for item in client.get("/jobs/last-runs").json()["jobs"]}["learned-audit"]
    assert ran["result"].startswith("checked 2, retired 1") and ran["label"] == "Check what it learned"
    last = client.get("/learned/audit/last").json()
    assert last["run"] == out["run"] and [row["id"] for row in last["retired"]] == [joke_id]
    body = {"run": out["run"]}
    undone = client.post("/learned/audit/undo", json=body).json()
    redone = client.post("/learned/audit/redo", json=body).json()
    again = client.post("/learned/audit/undo", json=body).json()
    assert (undone, redone, again) == ({"restored": 1}, {"retired": 1}, {"restored": 1})
    fetched = client.get(f"/learned/{joke_id}")
    flags = client.get("/learned/audit/flags").json()
    assert fetched.status_code == 200 and flags == {"flags": {}}


def test_the_ledger_says_what_went_and_why(client, session):
    _seed(session)
    client.post("/learned/audit/run")
    lines = [line["text"] for item in jobruns.finished() if item["kind"] == "learned-audit" for line in item.get("lines", [])]
    assert any("Retired" in text and "tagged joke" in text for text in lines), lines


def test_the_pass_is_a_scheduled_job_run_by_the_autonomous_pass(session, monkeypatch):
    from tessellate.ai import autonomous
    from tessellate.core import passes

    assert "learned-audit" in passes.PASS_KINDS and "learned-audit" in passes.RUNNERS
    assert "after the night shift" in passes.schedule("learned-audit")
    calls = []
    monkeypatch.setattr(run, "run_job", lambda: calls.append(1))

    class Config:
        def get_preference(self, key, default=None):
            return default

    autonomous._stage_learned_audit(Config())
    assert calls == [1]
    Config.get_preference = lambda self, key, default=None: False if key == "learn.night_shift.enabled" else default
    autonomous._stage_learned_audit(Config())
    assert calls == [1]


def test_run_now_runs_the_pass_as_a_job(client, session):
    from tessellate.core import passes

    joke_id, _ = _seed(session)
    passes.run_pass("learned-audit")
    ran = {item["kind"]: item for item in client.get("/jobs/last-runs").json()["jobs"]}["learned-audit"]
    assert ran["result"] == "checked 2, retired 1" and ran["can_run"] is True
    session.expire_all()
    assert session.get(DerivedFact, joke_id).deleted_at is not None
