"""Tidy: rule-based reviews of notes, links, tags and reminders, no model
needed (INBOX 691, decisions 2 and 3).

Each review lists what it found with a one-line why and a preview of the
change, applies to the rows a person ticked, and undoes the whole batch in
one call. The rules are pure functions first (`entry/tidy.py`), tested here
without a database, then each review end to end through `/tidy`.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta


from tessellate.core import deps, events
from tessellate.core.database import Entry, EntryLink, Reminder
from tessellate.entry import manager, tidy

# --- the pure rules -------------------------------------------------------------


def test_lookalike_key_sets_case_spacing_and_plurals_aside():
    assert tidy.lookalike_key("Study schedule") == tidy.lookalike_key("study-schedule")
    assert tidy.lookalike_key("ideas") == tidy.lookalike_key("Idea")
    assert tidy.lookalike_key("to_do") == tidy.lookalike_key("todo")
    assert tidy.lookalike_key("stories") == tidy.lookalike_key("story")
    assert tidy.lookalike_key("glass") != tidy.lookalike_key("glas")


def test_lookalike_groups_put_the_busiest_name_first():
    groups = tidy.lookalike_groups({"study-schedule": 1, "Study schedule": 4, "gym": 3})
    assert groups == [["Study schedule", "study-schedule"]]


def test_short_notes():
    assert tidy.is_short("")
    assert tidy.is_short("   \n# ")
    assert tidy.is_short("todo")
    assert tidy.is_short("buy milk")
    assert not tidy.is_short("Call the plumber about the leak")
    assert not tidy.is_short("![sketch](/uploads/a.png)")


def test_tag_fit_is_one_when_the_note_says_it():
    assert tidy.tag_fit("lisbon", {"lisbon", "hotel"}, peers_with=0, peers=10) == 1.0
    assert tidy.tag_fit("study schedule", {"study", "schedule", "gym"}, peers_with=0, peers=4) == 1.0


def test_tag_fit_otherwise_is_how_common_it_is_among_the_category():
    assert tidy.tag_fit("travel", {"hotel"}, peers_with=3, peers=12) == 0.25
    assert tidy.tag_fit("travel", {"hotel"}, peers_with=0, peers=0) == 0.0


# --- the API ---------------------------------------------------------------------


def _save(client, content, **extra):
    response = client.post("/entries", json={"content": content, **extra})
    assert response.status_code == 201, response.text
    return response.json()


def _review(client, key, **params):
    response = client.get(f"/tidy/{key}", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def _apply(client, key, ids, **extra):
    response = client.post(f"/tidy/{key}/apply", json={"ids": ids, **extra})
    assert response.status_code == 200, response.text
    return response.json()


def _undo(client, undo_id):
    response = client.post(f"/tidy/undo/{undo_id}")
    assert response.status_code == 200, response.text
    return response.json()


def test_the_summary_names_every_review_with_a_count(client):
    body = client.get("/tidy").json()
    keys = [r["key"] for r in body["reviews"]]
    assert keys == [
        "link-reasons",
        "weak-links",
        "auto-tags",
        "rare-tags",
        "lookalike-tags",
        "uncategorised",
        "duplicates",
        "similar-categories",
        "category-names",
        "short-notes",
        "stale-reminders",
    ]
    for review in body["reviews"]:
        assert review["label"] and review["about"]
        assert "\u2014" not in review["about"] and "!" not in review["about"]
        assert isinstance(review["count"], int)
        assert review["auto"] is False
    assert body["total"] == sum(r["count"] for r in body["reviews"])


def test_an_unknown_review_is_a_404(client):
    missing = client.get("/tidy/nope")
    assert missing.status_code == 404
    refused = client.post("/tidy/nope/apply", json={"ids": []})
    assert refused.status_code == 404


def test_link_reasons_names_generic_links_and_undoes(client, session):
    a = _save(client, "Trains\nThe Alfa Pendular from Lisbon to Porto", tags=["portugal"])
    b = _save(client, "Flights\nLand in Lisbon, train to Porto", tags=["portugal"])
    session.add(
        EntryLink(source_entry_id=a["id"], target_entry_id=b["id"], reason="similar in meaning", reason_confidence=0.7)
    )
    #: A person's words are never touched, even when they are vague.
    c = _save(client, "Packing list", tags=["portugal"])
    session.add(EntryLink(source_entry_id=a["id"], target_entry_id=c["id"], reason="similar in meaning"))
    session.commit()

    rows = _review(client, "link-reasons")["rows"]
    assert len(rows) == 1
    assert rows[0]["change"] == "Both tagged #portugal; both mention Lisbon and Porto"
    assert rows[0]["detail"] == "Similar in meaning, some likeness (70%)"

    done = _apply(client, "link-reasons", [rows[0]["id"]])
    assert done["applied"] == 1
    link = session.query(EntryLink).filter_by(target_entry_id=b["id"]).one()
    #: A stored reason reads as plain words (audit 1030 Z42, `database.plain_reason`).
    assert link.reason == "Both tagged portugal; both mention Lisbon and Porto"
    assert link.reason_confidence == 0.7
    assert _review(client, "link-reasons")["rows"] == []

    assert _undo(client, done["undo_id"])["restored"] == 1
    session.expire_all()
    link = session.query(EntryLink).filter_by(target_entry_id=b["id"]).one()
    assert link.reason == "similar in meaning"
    #: Twice is harmless.
    assert _undo(client, done["undo_id"])["restored"] == 0


def test_weak_links_lists_generic_weak_links_and_unlinks_with_undo(client, session):
    a = _save(client, "first thought")
    b = _save(client, "second thought")
    c = _save(client, "third thought")
    session.add_all([
        EntryLink(source_entry_id=a["id"], target_entry_id=b["id"], reason="similar in meaning", reason_confidence=0.58),
        EntryLink(source_entry_id=a["id"], target_entry_id=c["id"], reason="similar in meaning", reason_confidence=0.81),
    ])
    session.commit()

    rows = _review(client, "weak-links")["rows"]
    assert [r["detail"] for r in rows] == ["Similar in meaning, weak likeness (58%)"]
    assert rows[0]["change"] == "Unlink"
    assert len(_review(client, "weak-links", level="some")["rows"]) == 1
    assert len(_review(client, "weak-links", level="strong")["rows"]) == 2

    done = _apply(client, "weak-links", [rows[0]["id"]])
    assert done["applied"] == 1
    assert session.query(EntryLink).filter_by(target_entry_id=b["id"]).count() == 0
    #: The notes it touched, so the app patches two rows and does not re-read
    #: the notebook (tests/test_refresh_entries.py).
    assert done["entry_ids"] == sorted([a["id"], b["id"]])

    undone = _undo(client, done["undo_id"])
    assert undone["entry_ids"] == done["entry_ids"]
    session.expire_all()
    back = session.query(EntryLink).filter_by(target_entry_id=b["id"]).one()
    assert back.reason == "similar in meaning" and back.reason_confidence == 0.58


def test_auto_tags_lists_tags_another_actor_added_that_fit_poorly(client, session):
    a = _save(client, "Hotel near the river", category="Travel")
    entry = session.get(Entry, a["id"])
    with events.acting_as("ai:tag_notes"):
        manager.update_entry(session, entry, tags=["gardening", "hotel"])
    #: A person's own tag is never listed, however poorly it fits.
    b = _save(client, "Another note", category="Travel", tags=["misc"])

    rows = _review(client, "auto-tags")["rows"]
    assert [r["title"] for r in rows] == ["#gardening"]
    assert "not in its words" in rows[0]["detail"]
    assert rows[0]["change"] == "Remove #gardening from this note"

    done = _apply(client, "auto-tags", [rows[0]["id"]])
    session.expire_all()
    assert json.loads(session.get(Entry, a["id"]).tags) == ["hotel"]
    _undo(client, done["undo_id"])
    session.expire_all()
    assert json.loads(session.get(Entry, a["id"]).tags) == ["gardening", "hotel"]
    assert json.loads(session.get(Entry, b["id"]).tags) == ["misc"]
    #: Undone, the tag is still the one Atlas added: Tidy's writes are its own.
    assert [r["title"] for r in _review(client, "auto-tags")["rows"]] == ["#gardening"]


def test_auto_tags_skips_a_note_whose_tags_the_person_changed_since(client, session):
    a = _save(client, "Hotel near the river", category="Travel")
    entry = session.get(Entry, a["id"])
    with events.acting_as("ai:tag_notes"):
        manager.update_entry(session, entry, tags=["gardening"])
    client.put(f"/entries/{a['id']}", json={"tags": ["gardening", "river"]})
    assert _review(client, "auto-tags")["rows"] == []


def test_rare_tags_and_lookalike_tags(client, session):
    _save(client, "one", tags=["Study schedule", "solo"])
    _save(client, "two", tags=["Study schedule"])
    _save(client, "three", tags=["study-schedule"])

    rare = _review(client, "rare-tags")["rows"]
    assert sorted(r["title"] for r in rare) == ["#solo", "#study-schedule"]

    looks = _review(client, "lookalike-tags")["rows"]
    assert len(looks) == 1
    assert looks[0]["change"] == "Merge #study-schedule into #Study schedule"
    done = _apply(client, "lookalike-tags", [looks[0]["id"]])
    tags = sorted(t for e in session.query(Entry).all() for t in json.loads(e.tags))
    assert tags == ["Study schedule", "Study schedule", "Study schedule", "solo"]
    _undo(client, done["undo_id"])
    session.expire_all()
    tags = sorted(t for e in session.query(Entry).all() for t in json.loads(e.tags))
    assert tags == ["Study schedule", "Study schedule", "solo", "study-schedule"]

    solo = next(r for r in _review(client, "rare-tags")["rows"] if r["title"] == "#solo")
    _apply(client, "rare-tags", [solo["id"]])
    assert all("solo" not in json.loads(e.tags) for e in session.query(Entry).all())


def test_uncategorised_offers_the_category_the_words_point_to(client, session):
    for text in ("sourdough starter feeding", "sourdough loaf proving", "sourdough crumb notes"):
        _save(client, text, category="Baking")
    loose = _save(client, "sourdough starter smells sour", category="Uncategorised")
    vague = _save(client, "zzz qqq", category="Uncategorised")

    rows = {r["entry_ids"][0]: r for r in _review(client, "uncategorised")["rows"]}
    assert rows[loose["id"]]["change"] == "Move to Baking"
    assert rows[loose["id"]]["selectable"] is True
    assert rows[vague["id"]]["selectable"] is False

    done = _apply(client, "uncategorised", [rows[loose["id"]]["id"], rows[vague["id"]]["id"]])
    assert done["applied"] == 1
    moved = client.get(f"/entries/{loose['id']}").json()
    assert moved["category"] == "Baking"
    _undo(client, done["undo_id"])
    back = client.get(f"/entries/{loose['id']}").json()
    assert back["category"] == "Uncategorised"


def test_duplicates_merge_without_a_model_and_undo(client, session):
    a = _save(client, "Call the plumber about the kitchen leak on Monday", tags=["home"])
    b = _save(client, "Call the plumber about the kitchen leak on Monday morning", tags=["urgent"])
    rows = _review(client, "duplicates")["rows"]
    assert len(rows) == 1
    assert rows[0]["change"] == "Merge into one note; the other goes to the bin"

    done = _apply(client, "duplicates", [rows[0]["id"]])
    session.expire_all()
    keeper = session.get(Entry, a["id"])
    assert "morning" in keeper.content and json.loads(keeper.tags) == ["home", "urgent"]
    assert session.get(Entry, b["id"]).is_deleted

    _undo(client, done["undo_id"])
    session.expire_all()
    assert session.get(Entry, a["id"]).content == "Call the plumber about the kitchen leak on Monday"
    assert json.loads(session.get(Entry, a["id"]).tags) == ["home"]
    assert not session.get(Entry, b["id"]).is_deleted


def test_short_notes_go_to_the_bin_and_come_back(client, session):
    short = _save(client, "todo")
    _save(client, "A proper note about the garden fence")
    pinned = _save(client, "keep")
    session.get(Entry, pinned["id"]).pinned = True
    session.commit()
    rows = _review(client, "short-notes")["rows"]
    assert [r["entry_ids"] for r in rows] == [[short["id"]]]
    done = _apply(client, "short-notes", [rows[0]["id"]])
    session.expire_all()
    assert session.get(Entry, short["id"]).is_deleted
    _undo(client, done["undo_id"])
    session.expire_all()
    assert not session.get(Entry, short["id"]).is_deleted


def test_a_dismissed_row_stays_gone_and_comes_back_on_undismiss(client, session):
    """INBOX 783 ("how do I delete a suggestion??"): a row dismissed for good is
    not listed again, not counted, not applied, and Undo puts it back."""
    short = _save(client, "todo")
    other = _save(client, "buy milk")
    rows = _review(client, "short-notes")["rows"]
    assert len(rows) == 2
    target = next(r["id"] for r in rows if r["entry_ids"] == [short["id"]])
    shown = client.post("/tidy/short-notes/dismiss", json={"ids": [target, "nonsense"]})
    assert shown.status_code == 200 and shown.json()["dismissed"] == 1
    after = _review(client, "short-notes")
    assert [r["entry_ids"] for r in after["rows"]] == [[other["id"]]]
    counts = {r["key"]: r["count"] for r in client.get("/tidy").json()["reviews"]}
    assert counts["short-notes"] == 1
    assert _apply(client, "short-notes", [target])["applied"] == 0
    # Dismissing twice is the same as once.
    again = client.post("/tidy/short-notes/dismiss", json={"ids": [target]})
    assert again.status_code == 200
    back = client.post("/tidy/short-notes/undismiss", json={"ids": [target]})
    assert back.status_code == 200 and back.json()["dismissed"] == 0
    assert len(_review(client, "short-notes")["rows"]) == 2


def test_dismissing_in_an_unknown_review_is_a_404(client):
    refused = client.post("/tidy/nope/dismiss", json={"ids": ["note:1"]})
    assert refused.status_code == 404


def test_stale_reminders_are_marked_done_with_undo(client, session):
    old = Reminder(text="Renew passport", due_at=datetime.now() - timedelta(days=40))
    recent = Reminder(text="Water plants", due_at=datetime.now() - timedelta(days=2))
    repeating = Reminder(text="Bins", due_at=datetime.now() - timedelta(days=40), recurring="weekly")
    session.add_all([old, recent, repeating])
    session.commit()
    rows = _review(client, "stale-reminders")["rows"]
    assert [r["title"] for r in rows] == ["Renew passport"]
    done = _apply(client, "stale-reminders", [rows[0]["id"]])
    session.expire_all()
    assert session.get(Reminder, old.id).done
    assert done["entry_ids"] == [], "a reminder is not a note"
    _undo(client, done["undo_id"])
    session.expire_all()
    assert not session.get(Reminder, old.id).done


def test_apply_acts_only_on_rows_the_rule_still_finds(client, session):
    short = _save(client, "todo")
    done = _apply(client, "short-notes", [f"note:{short['id']}", "note:999999", "nonsense"])
    assert done["applied"] == 1


def test_history_lists_each_run_with_its_undo(client, session):
    short = _save(client, "todo")
    rows = _review(client, "short-notes")["rows"]
    done = _apply(client, "short-notes", [rows[0]["id"]])
    history = client.get("/tidy/history").json()["runs"]
    assert history[0]["undo_id"] == done["undo_id"]
    assert history[0]["review"] == "short-notes"
    assert history[0]["automatic"] is False
    assert history[0]["undone"] is False
    _undo(client, done["undo_id"])
    runs = client.get("/tidy/history").json()["runs"]
    assert runs[0]["undone"] is True
    assert short


def test_automatic_rules_are_off_by_default_and_run_after_filing(client, session):
    refused = client.put("/tidy/auto", json={"key": "duplicates", "on": True})
    assert refused.status_code == 400
    switched = client.put("/tidy/auto", json={"key": "stale-reminders", "on": True}).json()
    assert switched["auto"] is True
    session.add(Reminder(text="Renew passport", due_at=datetime.now() - timedelta(days=40)))
    session.commit()

    ran = tidy.run_automatic(deps.get_db().session(), force=True)
    assert ran == {"stale-reminders": 1}
    runs = client.get("/tidy/history").json()["runs"]
    assert runs[0]["automatic"] is True
    reviews = client.get("/tidy").json()["reviews"]
    assert reviews[-1]["auto"] is True


def test_the_link_reason_pass_runs_as_a_job_and_can_be_undone(client, session):
    a = _save(client, "Trains\nThe Alfa Pendular to Porto", tags=["portugal"])
    b = _save(client, "Flights\nThen the train to Porto", tags=["portugal"])
    session.add(EntryLink(source_entry_id=a["id"], target_entry_id=b["id"], reason="similar in meaning", reason_confidence=0.7))
    session.commit()
    #: A Quit-all an earlier test in this worker sent stops a pass that has
    #: not started yet, by design; this one is asked to run.
    tidy._stop.clear()

    result = tidy.respecify_all("default")
    assert result["named"] == 1
    session.expire_all()
    assert session.query(EntryLink).one().reason.startswith("Both tagged portugal")
    _undo(client, result["undo_id"])
    session.expire_all()
    assert session.query(EntryLink).one().reason == "similar in meaning"


def test_the_link_reason_pass_stops_when_asked(client, session):
    for i in range(3):
        a = _save(client, f"Trains {i}", tags=[f"trip-{i}"])
        b = _save(client, f"Flights {i}", tags=[f"trip-{i}"])
        session.add(EntryLink(source_entry_id=a["id"], target_entry_id=b["id"], reason="similar in meaning", reason_confidence=0.7))
    session.commit()
    tidy.request_stop()
    result = tidy.respecify_all("default", chunk=1)
    assert result["stopped"] is True
    assert result["named"] < 3


def test_new_links_made_by_similarity_get_specific_reasons(ai_client, session):
    """Decision 1 at the source: a link made without words now says what the
    two notes share (the deduction in `manager._deduce_reason`)."""
    a = _save(ai_client, "a funny scarecrow joke", tags=["jokes"])
    b = _save(ai_client, "another funny pun", tags=["jokes"])
    link = ai_client.post(f"/entries/{a['id']}/links", json={"target_id": b["id"]}).json()["links"][0]
    assert link["reason"].startswith("Both tagged #jokes")
def test_each_review_has_a_finds_line_and_a_description_that_names_its_change(client):
    """INBOX 718: the overview row carries `finds` (what the rule looks for),
    the review's own page `about` (which names what the button changes)."""
    for review in client.get("/tidy").json()["reviews"]:
        assert review["finds"] and review["finds"].endswith(".")
        assert len(review["finds"]) <= 60, review["finds"]
        assert "\u2014" not in review["finds"] and "!" not in review["finds"]
        assert review["finds"] != review["about"]


def test_the_badge_count_for_uncategorised_does_not_run_the_per_note_matcher(client, session, monkeypatch):
    """Audit 2026-10-10: `GET /tidy` (the Notes dock's badge, fetched on every
    list redraw) took 23 s at 5,000 notes, 11.5 s of it matching each loose
    note against the others only to count it. The count is the number of
    uncategorised notes, whichever branch each row takes, so it needs no match;
    the review's own list still does."""
    from tessellate.ai import lexical_filing

    for text in ("sourdough starter feeding", "sourdough loaf proving"):
        _save(client, text, category="Baking")
    _save(client, "sourdough starter smells sour", category="Uncategorised")
    _save(client, "zzz qqq", category="Uncategorised")
    listed = len(_review(client, "uncategorised")["rows"])

    def refuse(*_a, **_k):
        raise AssertionError("the badge must not match each note")

    monkeypatch.setattr(lexical_filing, "lexical_category", refuse)
    counts = {r["key"]: r["count"] for r in client.get("/tidy").json()["reviews"]}
    assert counts["uncategorised"] == listed == 2


def test_the_duplicates_count_is_kept_until_the_notebook_changes(client, session, monkeypatch):
    """Audit 2026-10-10: the scan is quadratic and the badge asks on every
    redraw, so an unchanged notebook answers from the last scan; any new note,
    edit or deletion is a different notebook and scans again."""
    from tessellate.entry import duplicates

    calls = []
    real = duplicates.find_duplicates

    def counted(*args, **kwargs):
        calls.append(1)
        return real(*args, **kwargs)

    monkeypatch.setattr(duplicates, "find_duplicates", counted)
    tidy._duplicates_seen.clear()
    first = _save(client, "Call the plumber about the kitchen leak on Monday")
    _save(client, "Call the plumber about the kitchen leak on Monday morning")
    assert client.get("/tidy").json()["reviews"][6]["count"] == 1
    assert client.get("/tidy").json()["reviews"][6]["count"] == 1
    assert len(calls) == 1, "an unchanged notebook must not be scanned twice"

    client.put(f"/entries/{first['id']}", json={"content": "Something else entirely about gardening tools"})
    assert client.get("/tidy").json()["reviews"][6]["count"] == 0
    assert len(calls) == 2, "an edit is a different notebook"


def test_a_sensitive_note_is_listed_unticked_and_never_moved_by_itself(session, app_state):
    """WORLD_CLASS 23, decision 6: a note that reads as health is suggested
    in Tidy with its why, unticked, and the automatic run leaves it alone."""
    from tessellate.core import deps

    for text in ("Dentist check-up booked for the 21st", "GP says blood pressure is fine", "Physio for the shoulder"):
        manager.create_entry(session, text, category_name="Health")
    held = manager.create_entry(session, "Dentist appointment moved to Friday", category_name=manager.UNCATEGORISED)
    session.commit()
    row = next(r for r in tidy.rows(session, "uncategorised") if r["id"] == f"note:{held.id}")
    assert row["change"] == "Move to Health" and row["selectable"] and not row["ticked"]
    assert row["detail"].startswith("Waits for you: it reads as") and "dentist" in row["detail"]
    tidy.set_auto(deps.get_config(), "uncategorised", True)
    tidy.run_automatic(session, force=True)
    session.refresh(held)
    assert manager.category_name_for(session, held) == manager.UNCATEGORISED
