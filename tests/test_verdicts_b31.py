"""B31 "Wrong fact" and B32 "Pin as true" (CHAT_PLAN): the person's word on
a cited line's own sentence, from the next turn on. Wrong: not quoted, and
no insight quoting it is volunteered. Pinned: said as theirs with the day,
and no inference quoting it beside it. Each is a learned row whose Delete is
the undo, and a model reads the same verdicts written into its notes."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from tests import _gold
from tessellate.ai import verdicts
from tessellate.core.database import Entry
from tessellate.entry import manager
from tests.test_composer_route_688 import _ask

ROOT = Path(__file__).resolve().parents[1]
Q1 = "What have I saved about courses & study?"
BODY = {"notes_only": True, "use_tools": False, "answer_from": "notes"}


def _seed(session) -> None:
    for n in _gold.load()["notes"]:
        made = manager.create_entry(session, n["content"], category_name=n["category"], tags=n["tags"])
        session.flush()
        row = session.get(Entry, made.id)
        row.created_at = row.updated_at = datetime.fromisoformat(n["date"] + "T10:00:00")
    session.commit()


def _row(out: dict, words: str) -> dict:
    """The line saying `words`, as the peek has it."""
    return next(r for r in out["grounding"][0]["sentences"] if words in r["sentence"])


def _mark(client, verdict: str, row: dict):
    """What the peek sends: one verdict a sentence the line was made from."""
    made = None
    for part in row.get("parts") or [row]:
        made = client.post("/learned/verdict", json={
            "verdict": verdict, "note_id": part["note_id"], "sentence": part["source"],
            "start": part["start"], "end": part["end"], "line": row["sentence"],
        })
        assert made.status_code == 201, made.text
    return made


def test_a_wrong_fact_is_not_quoted_next_turn_and_delete_undoes_it(client, session):
    _seed(session)
    before = _ask(client, Q1, **BODY)
    assert "big O" in before["text"]
    made = _mark(client, "wrong", _row(before, "big O"))
    assert made.status_code == 201
    after = _ask(client, Q1, **BODY)
    assert "big O" not in after["text"]
    assert "linked lists" not in after["text"] or "shaky" not in after["text"]
    listed = client.get("/learned", params={"kind": "wrong"}).json()
    assert any(row["id"] == made.json()["id"] for row in listed["items"]), listed
    undone = client.delete(f"/learned/{made.json()['id']}")
    assert undone.status_code == 204
    assert "big O" in _ask(client, Q1, **BODY)["text"]


def test_a_pinned_line_is_said_as_theirs_and_beats_the_inference(client, session):
    _seed(session)
    before = _ask(client, Q1, **BODY)
    assert "no later note says how that went" in before["text"]
    made = _mark(client, "pinned", _row(before, "25 minutes"))
    assert made.status_code == 201
    after = _ask(client, Q1, **BODY)
    assert after["text"].count("(you pinned this as true, ") == 1
    assert "no later note says how that went" not in after["text"]


def test_a_sentence_the_note_no_longer_holds_is_refused(client, session):
    _seed(session)
    out = _ask(client, Q1, **BODY)
    row = _row(out, "big O")
    refused = client.post("/learned/verdict", json={
        "verdict": "wrong", "note_id": row["note_id"], "sentence": "Something the note never said.", "start": 0, "end": 5,
    })
    assert refused.status_code == 422 and "no longer says" in refused.json()["detail"]


def test_a_model_reads_the_verdicts_written_into_its_notes():
    known = verdicts.Known(frozenset({(1, verdicts.norm("Still shaky on big O"))}), {(2, verdicts.norm("Going to try 25 minutes on, 5 off")): date(2026, 10, 11)})
    notes = [
        {"id": 1, "content": "Lab: got linked lists working. Still shaky on big O. Ask the tutor."},
        {"id": 2, "content": "Study plan: library on Wednesdays. Going to try 25 minutes on, 5 off."},
        {"id": 3, "content": "Untouched."},
    ]
    out = verdicts.for_model(notes, known)
    assert "big O" not in out[0]["content"] and "Ask the tutor." in out[0]["content"]
    assert out[1]["content"].endswith("5 off. [pinned as true by the person, 11 October]")
    assert out[2] is notes[2] and notes[0]["content"].count("big O") == 1


def test_the_peek_carries_the_two_buttons():
    js = (ROOT / "frontend/js/citation-peek.js").read_text(encoding="utf-8")
    body = js[js.index("function openCitationPeek("):js.index("function closeCitationPeek(")]
    assert "citationVerdictRow(source, content)" in body
    #: The row itself is built in the lazy ask-compose.js (the boot ratchet).
    lazy = (ROOT / "frontend/js/ask-compose.js").read_text(encoding="utf-8")
    row = lazy[lazy.index("//: **Wrong fact and Pin as true"):lazy.index("function askAnswerMenu(")]
    assert "Wrong fact" in row and "Pin as true" in row and "/learned/verdict" in row
