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
from tests._app_js import MOVED_OUT, frontend_text, with_pieces
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


def test_binning_or_hiding_one_note_keeps_the_confirmation(client, session):
    """Review of B9: a confirmation rests on all its notes, not the newest
    one, so binning (or making private) one of four keeps it and offers no
    second Confirm. Only when none of them can be opened is it hidden."""
    item = _confirmed(client, session)
    newest = max(note["id"] for note in item["notes"])
    session.get(Entry, newest).is_deleted = True
    session.commit()
    items = client.get("/insights/confirmed").json()["items"]
    assert [i["id"] for i in items] == [item["id"]] and len(items[0]["notes"]) == 3
    assert _golf(client)["confirmed"] and _golf(client)["confirmed_id"] == item["id"]
    session.get(Entry, newest).is_deleted = False
    session.get(Entry, newest).is_private = True
    session.commit()
    listed = client.get("/insights/confirmed").json()["items"]
    edited = client.patch(f"/insights/confirmed/{item['id']}", json={"sentence": "Golf is mine"})
    assert [i["id"] for i in listed] == [item["id"]] and edited.status_code == 200


def test_confirm_again_writes_no_second_row(client, session):
    item = _confirmed(client, session)
    again = client.post("/insights/confirm", json={**_golf(client), "confirmed": False})
    assert again.status_code == 201 and again.json()["id"] == item["id"]
    assert len(session.scalars(select(DerivedFact).where(DerivedFact.kind == "confirmed")).all()) == 1


def test_undo_of_remove_after_a_new_confirm_leaves_one_row(client, session):
    """Remove, Confirm again from Tidy, then Ctrl+Z on the Remove: the old
    row (with its own wording) is back and the newer one goes, so one row."""
    item = _confirmed(client, session)
    client.patch(f"/insights/confirmed/{item['id']}", json={"sentence": "Golf is how I unwind"})
    removed = client.delete(f"/insights/confirmed/{item['id']}")
    assert removed.status_code == 200
    newer = client.post("/insights/confirm", json=_golf(client)).json()["id"]
    assert newer != item["id"]
    back = client.post(f"/insights/confirmed/{item['id']}/restore")
    listed = client.get("/insights/confirmed").json()["items"]
    assert back.status_code == 200 and back.json()["sentence"] == "Golf is how I unwind"
    assert [i["id"] for i in listed] == [item["id"]]
    assert _golf(client)["confirmed_id"] == item["id"]


def test_a_new_subject_replaces_the_one_before(client, session):
    """Change what it is about names it anew: the word before stops
    answering; the tag it was found under still does (its Patterns line)."""
    item = _confirmed(client, session)
    for word in ("disc golf", "frisbee"):
        renamed = client.patch(f"/insights/confirmed/{item['id']}", json={"subject": word})
        assert renamed.status_code == 200
    subjects = insights.memory(session).subjects()
    assert "frisbee" in subjects and "golf" in subjects and "disc golf" not in subjects
    #: Back to the tag's own word: nothing extra answers.
    client.patch(f"/insights/confirmed/{item['id']}", json={"subject": "golf"})
    assert set(insights.memory(session).subjects()) == {"golf"}


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
    #: Its own lazy file, not a piece moved out of status.js.
    assert "confirmed-patterns.js" not in MOVED_OUT["status.js"]
    status = frontend_text("confirmed-patterns.js")
    items = status[status.index("function confirmedPatternItems(") :][:3600]
    #: Not right is the pair's own item (one wording, `INSIGHT_VERDICT_ITEMS`).
    for label in ("ph:pencil-simple Edit", 'item.verdict === "dismiss").label', "ph:trash Remove"):
        assert label in items, label
    #: Remove and Not right each go on the undo stack (the history menu).
    assert items.count("offerUndo(") >= 2
    #: A subject change goes on the undo stack too, and every change redraws
    #: the dashboard's Patterns line wherever it was made.
    assert 'field === "sentence" &&' not in items and "pushRequestUndo(" in items
    assert "renderDashSubmessage()" in items
    tidy = with_pieces("tidy.js")
    #: A confirmed plan's Done is in the same menu, not a button beside it.
    patterns = tidy[tidy.index("async function tidyPatterns(") :][:2400]
    assert "kebabMenu([...done, ...confirmedPatternItems(" in patterns
    assert 'pattern.rule !== "drift"' not in patterns
    day = with_pieces("dash-day.js")
    assert "confirmedPatternItems(" in day[day.index("function dashPatternBit(") :][:1600]
    #: Lazy (the boot gzip budget): each caller loads it before drawing one.
    for caller in ("settings-controls.js", "tidy.js", "dash-day.js"):
        assert 'lazyScript("/js/confirmed-patterns.js")' in open(f"frontend/js/{caller}", encoding="utf-8").read(), caller
