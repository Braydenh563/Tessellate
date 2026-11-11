"""Ask when unsure (the owner, 2026-11-11, HANDOVER decision 6: "an 'ask when
unsure' choice the person turns on in Settings, perhaps a small filing
options menu on the capture tab").

Off by default. On, a filing whose confidence is under
`lexical_filing.UNSURE_LINE` is not applied: the note waits in Uncategorised
and the capture shows the top choices to pick from, the way a close call
already does. Consent: nothing under the line moves the note by itself.
Measured on the 120-note filing fixture, filed leave-one-out.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from tessellate.ai import janitor, lexical_filing
from tessellate.core.database import Entry
from tessellate.entry import manager

NOTES = json.loads((Path(__file__).parent / "fixtures" / "filing" / "notes.json").read_text(encoding="utf-8"))


def _seed(session) -> list[int]:
    ids = [manager.create_entry(session, note["content"], category_name=note["category"]).id for note in NOTES]
    session.commit()
    return ids


def _filed_by_words(session, ids):
    """(index, decision) for every note the words file with the setting off."""
    out = []
    for i, (entry_id, note) in enumerate(zip(ids, NOTES)):
        decision = lexical_filing.decide(session, note["content"], exclude_entry_id=entry_id)
        if decision.filed is not None:
            out.append((i, decision))
    return out


def test_it_is_off_by_default(app_state) -> None:
    assert lexical_filing.ask_when_unsure() is False
    assert lexical_filing.is_unsure(10) is False


def test_on_a_filing_under_the_line_waits_and_one_over_it_files(session, app_state) -> None:
    ids = _seed(session)
    before = _filed_by_words(session, ids)
    app_state.set_preference("ask_when_unsure", True)
    held = kept = 0
    for i, base in before:
        now = lexical_filing.decide(session, NOTES[i]["content"], exclude_entry_id=ids[i])
        if base.confidence < lexical_filing.UNSURE_LINE:
            held += 1
            assert now.filed is None and now.unsure, (i, base.confidence)
            #: What it would have filed is still first among the choices.
            assert now.ranked[0].name == base.filed.name
        else:
            kept += 1
            assert now.filed is not None and now.filed.name == base.filed.name and not now.unsure
    assert held >= 5 and kept >= 20, (held, kept)


def test_the_filing_call_offers_the_choices_and_says_why(session, app_state) -> None:
    ids = _seed(session)
    i, base = next((i, d) for i, d in _filed_by_words(session, ids) if d.confidence < lexical_filing.UNSURE_LINE)
    app_state.set_preference("ask_when_unsure", True)
    call = lexical_filing.filing_call(session, NOTES[i]["content"], exclude_entry_id=ids[i])
    assert call.category is None
    assert call.choices and call.choices[0][0] == base.filed.name
    assert 1 <= len(call.choices) <= lexical_filing.CHOICES
    assert call.why == lexical_filing.ASK_WHY and call.why.startswith("You asked")


def test_a_model_or_meaning_pick_under_the_line_is_held_too(app_state) -> None:
    pick = ("Work", lexical_filing.UNSURE_LINE - 1, "llm")
    sure = ("Work", lexical_filing.UNSURE_LINE + 10, "llm")
    assert janitor._unless_held("a plain note", pick) == pick  # off: nothing changes
    app_state.set_preference("ask_when_unsure", True)
    assert janitor._unless_held("a plain note", pick) is None
    assert janitor._unless_held("a plain note", sure) == sure


def test_the_line_is_the_calibrated_number_and_zero_is_no_filing(app_state) -> None:
    app_state.set_preference("ask_when_unsure", True)
    assert lexical_filing.is_unsure(lexical_filing.UNSURE_LINE - 1)
    assert not lexical_filing.is_unsure(lexical_filing.UNSURE_LINE)
    assert not lexical_filing.is_unsure(0)


def test_the_setting_round_trips_and_the_saved_note_waits_with_choices(client, session) -> None:
    assert client.get("/preferences").json()["ask_when_unsure"] is False
    ids = _seed(session)
    #: A note taken out of the notebook, then read afresh: the first whose
    #: filing lands under the line is the one this test saves.
    for i, _ in _filed_by_words(session, ids):
        manager.soft_delete_entry(session, session.get(Entry, ids[i]))
        session.commit()
        base = lexical_filing.decide(session, NOTES[i]["content"])
        if base.filed is not None and base.confidence < lexical_filing.UNSURE_LINE:
            break
    else:
        raise AssertionError("no note files under the line")
    text = NOTES[i]["content"]

    def saved() -> dict:
        made = client.post("/entries", json={"content": text}).json()
        status = client.get(f"/entries/{made['id']}/filing").json()
        for _ in range(200):
            if status["filing_state"] != "pending":
                break
            time.sleep(0.02)
            status = client.get(f"/entries/{made['id']}/filing").json()
        #: Gone again, so the next save reads the same notebook as this one.
        session.expire_all()
        manager.soft_delete_entry(session, session.get(Entry, made["id"]))
        session.commit()
        return status

    off = saved()
    assert off["filed_by"] == "words" and off["category"] == base.filed.name
    assert client.put("/preferences", json={"ask_when_unsure": True}).json()["ask_when_unsure"] is True
    on = saved()
    assert on["filed_by"] == "none" and on["category"] == manager.UNCATEGORISED, on
    assert on["suggestions"][0] == base.filed.name
    assert on["waits_why"] == lexical_filing.ASK_WHY
