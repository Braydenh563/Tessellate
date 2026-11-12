"""WORLD_CLASS_PLAN I7's last half: "wrong" on an evidence card.

The person marks the passage an evidence card shows as wrong (the same
verdict a cited line's peek sends, `ai/verdicts.py`). It is a correction
(`learning.record`), What the notebook learned lists it, its Delete is the
undo, the next answer leaves the sentence out (`test_verdicts_b31.py`), and,
new here, the next filing does too: a note being re-filed is read without
the sentence, and a neighbour quoted as filing evidence is quoted without it.
"""

from __future__ import annotations

from tessellate.ai import learning, librarian, verdicts
from tessellate.entry import manager
from tests._app_js import app_js_text

WRONG = "The kiln budget belongs to the garden club."
BODY = f"Kiln rota for the pottery studio. {WRONG} Glaze orders go out on Friday."


def _filed(session, text, category):
    entry = manager.create_entry(session, text, category, [])
    session.commit()
    return entry


def _mark_wrong(session, entry):
    start = entry.content.index(WRONG)
    made = verdicts.mark(
        session, verdicts.WRONG, entry.id, WRONG, start, start + len(WRONG), line="The garden club pays for the kiln."
    )
    session.commit()
    return made


def test_a_note_re_filed_is_read_without_the_sentence_marked_wrong(app_state, session):
    note = _filed(session, BODY, "Studio")
    assert "garden club" in librarian.filing_prompt(session, BODY, ["Studio", "Garden"], exclude_entry_id=note.id)
    _mark_wrong(session, note)
    prompt = librarian.filing_prompt(session, BODY, ["Studio", "Garden"], exclude_entry_id=note.id)
    note_part = prompt.split("Note:")[-1]
    assert "garden club" not in note_part
    assert "Kiln rota" in note_part and "Glaze orders" in note_part


def test_a_neighbour_quoted_as_filing_evidence_is_quoted_without_it(app_state, session):
    neighbour = _filed(session, BODY, "Studio")
    _mark_wrong(session, neighbour)
    prompt = librarian.filing_prompt(session, "kiln rota glaze orders for the pottery studio", ["Studio", "Garden"])
    evidence = prompt.split("Note:")[0]
    assert "is in Studio" in evidence and "Kiln rota" in evidence
    assert "garden club" not in evidence


def test_the_mark_is_a_correction_and_its_delete_undoes_it_for_filing(app_state, client, session):
    note = _filed(session, BODY, "Studio")
    made = _mark_wrong(session, note)
    assert any(c.kind == "wrong_fact" for c in learning.corrections(session))
    listed = client.get("/learned", params={"kind": "wrong"}).json()
    assert any(row["id"] == made["id"] for row in listed["items"])
    deleted = client.delete(f"/learned/{made['id']}")
    assert deleted.status_code in (200, 204)
    session.expire_all()
    prompt = librarian.filing_prompt(session, BODY, ["Studio"], exclude_entry_id=note.id)
    assert "garden club" in prompt.split("Note:")[-1]


def test_each_evidence_card_carries_the_verdict_pair_outside_its_button():
    js = app_js_text()
    start = js.index("function renderEvidenceView(")
    body = js[start : js.index("\nfunction ", start + 10)]
    assert "evidenceCardVerdict(" in body, "each card gets Is this line right? with Confirm and Not right"
    # A button inside the card's button is not a button a screen reader can reach.
    assert "answer-evidence-item" in body
    helper = js[js.index("function evidenceCardVerdict(") :]
    helper = helper[: helper.index("\n}\n")]
    assert "citationVerdictRow(" in helper, "the one verdict pair a cited line's peek sends"
    assert 'ensureModule("askCompose")' in helper
