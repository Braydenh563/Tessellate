"""Confirmed patterns are managed (CHAT_PLAN B9, the owner 2026-11-05: "also
is there a way to edit or managed confirmed patterns??").

A Confirm writes a `derived_facts` row of kind "confirmed". Settings, What
it remembers lists them as their own group (the sentence, the day it was
confirmed, the notes behind it) with Edit (the wording or the subject, kept
as the person's own word and said by the composer), Remove (a soft delete
with Undo) and Not right (the dismiss path); the Patterns line's confirmed
rows carry the same three in their menu. Private notes and other spaces are
never listed or reached."""

from __future__ import annotations

from sqlalchemy import select

from tessellate.ai import insights
from tessellate.core.database import DerivedFact, Entry
from tests._app_js import with_pieces
from tests.test_composer_route_688 import _ask
from tests.test_insight_verdicts import _golf, _golf_notebook


def _confirmed(client, session) -> dict:
    _golf_notebook(session)
    done = client.post("/insights/confirm", json=_golf(client))
    assert done.status_code == 201
    items = client.get("/insights/confirmed").json()["items"]
    assert len(items) == 1
    return items[0]


def test_the_list_says_the_sentence_the_day_and_the_notes(client, session):
    item = _confirmed(client, session)
    assert item["sentence"] == "Golf is a hobby of yours"
    assert item["line"].startswith("Golf is a hobby of yours, as you told me on ")
    assert item["confirmed_on"] and item["subject"] == "golf" and item["rule"] == "recurrence"
    assert len(item["notes"]) == 4 and all(n["title"] for n in item["notes"])
    #: The Patterns line's confirmed row carries the id its menu acts on.
    assert _golf(client)["confirmed_id"] == item["id"]


def test_edit_the_wording_is_said_as_the_persons_word_from_the_next_turn(client, session):
    item = _confirmed(client, session)
    edited = client.patch(f"/insights/confirmed/{item['id']}", json={"sentence": "Golf is how I unwind after work."})
    assert edited.status_code == 200
    line = edited.json()["line"]
    #: Their words, the day it was first confirmed kept, one end mark.
    assert line.startswith("Golf is how I unwind after work, as you told me on ") and line.endswith(".")
    assert line.split(" on ")[-1] == item["line"].split(" on ")[-1]
    assert _golf(client)["text"] == line
    out = _ask(client, "tell me about golf", use_tools=False)
    assert out["text"].startswith(line), out["text"][:200]


def test_edit_the_subject_keeps_the_pattern_and_answers_the_new_word(client, session):
    item = _confirmed(client, session)
    edited = client.patch(f"/insights/confirmed/{item['id']}", json={"subject": "disc golf"})
    assert edited.status_code == 200 and edited.json()["subject"] == "disc golf"
    known = insights.memory(session)
    assert "disc golf" in known.subjects() and "golf" in known.subjects()
    #: The measured pattern is still the confirmed one, not shown again to confirm.
    assert _golf(client)["confirmed"]


def test_an_empty_or_subjectless_edit_is_refused(client, session):
    item = _confirmed(client, session)
    blank = client.patch(f"/insights/confirmed/{item['id']}", json={"sentence": "   "})
    nothing = client.patch(f"/insights/confirmed/{item['id']}", json={})
    assert blank.status_code == nothing.status_code == 422


def test_remove_is_a_soft_delete_and_undo_brings_it_back(client, session):
    item = _confirmed(client, session)
    removed = client.delete(f"/insights/confirmed/{item['id']}")
    assert removed.status_code == 200
    assert client.get("/insights/confirmed").json()["items"] == []
    row = session.get(DerivedFact, item["id"])
    session.refresh(row)
    assert row.deleted_at is not None
    #: Removed is not Not right: the pattern may be confirmed again.
    again = _golf(client)
    assert again and not again["confirmed"]
    back = client.post(f"/insights/confirmed/{item['id']}/restore")
    assert back.status_code == 200
    assert [i["id"] for i in client.get("/insights/confirmed").json()["items"]] == [item["id"]]
    assert _golf(client)["confirmed"]


def test_not_right_retires_it_and_keeps_the_pattern_away_with_undo(client, session):
    item = _confirmed(client, session)
    said = client.post(f"/insights/confirmed/{item['id']}/dismiss")
    assert said.status_code == 201
    assert client.get("/insights/confirmed").json()["items"] == []
    assert _golf(client) is None
    out = _ask(client, "tell me about golf", use_tools=False)
    assert not out["text"].startswith(item["line"])
    #: Undo: the fact is back and the dismissal taken out.
    back = client.post(f"/insights/confirmed/{item['id']}/restore")
    assert back.status_code == 200
    taken = [client.delete(f"/learned/corrections/{cid}").status_code for cid in said.json()["correction_ids"]]
    assert taken == [200]
    assert _golf(client)["confirmed"]


def test_a_private_note_hides_its_confirmed_pattern(client, session):
    item = _confirmed(client, session)
    for note in item["notes"]:
        session.get(Entry, note["id"]).is_private = True
    session.commit()
    assert client.get("/insights/confirmed").json()["items"] == []
    edited = client.patch(f"/insights/confirmed/{item['id']}", json={"sentence": "x y z"})
    removed = client.delete(f"/insights/confirmed/{item['id']}")
    assert edited.status_code == removed.status_code == 404
    assert not insights.memory(session).confirmed


def test_another_space_neither_lists_nor_reaches_it(client, session):
    item = _confirmed(client, session)
    space = client.post("/spaces", json={"name": "Uni"})
    assert space.json()["id"] == "uni"
    other = {"X-Workspace-ID": "uni"}
    assert client.get("/insights/confirmed", headers=other).json()["items"] == []
    edited = client.patch(f"/insights/confirmed/{item['id']}", json={"sentence": "x y z"}, headers=other)
    dismissed = client.post(f"/insights/confirmed/{item['id']}/dismiss", headers=other)
    assert edited.status_code == dismissed.status_code == 404
    assert session.scalars(select(DerivedFact).where(DerivedFact.deleted_at.is_(None))).one()


# --- the page ------------------------------------------------------------------------------


def test_settings_lists_them_as_their_own_group_with_the_three_actions():
    html = open("frontend/index.html", encoding="utf-8").read()
    section = html[html.index('id="settings-memory"') :][:6000]
    assert 'id="memory-confirmed-list"' in section and "Confirmed patterns" in section
    js = with_pieces("settings-controls.js")
    body = js[js.index("const drawConfirmed = async () => {") :][:2600]
    assert 'apiJson("/insights/confirmed")' in body
    assert "rowActions(confirmedPatternItems(" in body


def test_one_set_of_actions_for_settings_tidy_and_the_dashboard():
    status = with_pieces("status.js")
    items = status[status.index("function confirmedPatternItems(") :][:3200]
    #: Not right is the pair's own item (one wording, `INSIGHT_VERDICT_ITEMS`).
    for label in ("ph:pencil-simple Edit", 'item.verdict === "dismiss").label', "ph:trash Remove"):
        assert label in items, label
    #: Remove and Not right each go on the undo stack (the history menu).
    assert items.count("offerUndo(") >= 2
    tidy = with_pieces("tidy.js")
    assert "kebabMenu(confirmedPatternItems(" in tidy
    day = with_pieces("dash-day.js")
    assert "confirmedPatternItems(" in day[day.index("function dashPatternBit(") :][:1600]
    #: Lazy (the boot gzip budget): each caller loads it before drawing one.
    for caller in ("settings-controls.js", "tidy.js", "dash-day.js"):
        assert 'lazyScript("/js/confirmed-patterns.js")' in open(f"frontend/js/{caller}", encoding="utf-8").read(), caller
