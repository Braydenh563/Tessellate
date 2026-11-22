"""The entries service, called directly (decision 55: services are tested on
their own; the route tests stay as they were and prove nothing changed)."""

from __future__ import annotations

from datetime import date

from tessellate.entry import manager
from tessellate.entry import service


def _note(session, text: str):
    entry = manager.create_entry(session, text, category_name=manager.UNCATEGORISED)
    session.commit()
    return entry


def test_a_daily_note_is_found_by_its_first_line_only(session):
    assert service.daily_note(session, date(2026, 9, 13)) is None
    _note(session, "notes\n# 2026-09-13")
    assert service.daily_note(session, date(2026, 9, 13)) is None
    made = service.open_daily_note(session, date(2026, 9, 13))
    assert made.content.startswith("# 2026-09-13")
    assert service.open_daily_note(session, date(2026, 9, 13)).id == made.id


def test_the_streak_allows_today_to_be_empty(session):
    for day in ("2026-09-10", "2026-09-11", "2026-09-12"):
        service.open_daily_note(session, date.fromisoformat(day))
    session.commit()
    days, streak = service.journal(session, date(2026, 9, 13), 5)
    assert streak == 3
    assert [d.isoformat() for d, written in days if written] == ["2026-09-10", "2026-09-11", "2026-09-12"]
    assert days[-1] == (date(2026, 9, 13), False)


def test_a_private_note_is_named_by_the_private_label(session):
    entry = _note(session, "# Bread\nflour and water")
    assert service.connection_label(entry) == "Bread"
    entry.is_private = True
    assert service.connection_label(entry) == manager.PRIVATE_LABEL


def test_connections_fold_in_a_wiki_link_with_no_stored_link(session):
    target = _note(session, "# Sourdough starter\nfeed it daily")
    writer = _note(session, "see [[Sourdough starter]]")
    found = service.connections(session, writer, references=[])
    assert [row["id"] for row in found["outgoing"]] == [target.id]
    assert found["outgoing"][0]["reason"] == "Links to it"
    assert found["files"] == [] and found["boards"] == []


def test_connected_files_reads_only_referenced_uploads(session):
    assert service.connected_files(session, "no pictures here") == []


def test_stopping_a_settled_note_changes_nothing(session):
    entry = _note(session, "plain words")
    entry.filing_state = "done"
    stopped, category = service.stop_filing_one(session, entry, "keep")
    assert (stopped, category) == (False, manager.UNCATEGORISED)


def test_stopping_a_pending_note_marks_it_stopped(session):
    entry = _note(session, "plain words")
    entry.filing_state = "pending"
    stopped, _category = service.stop_filing_one(session, entry, "keep")
    assert stopped and entry.filing_state == manager.FILING_STOPPED


def test_accepting_a_filing_makes_it_the_persons_and_logs_once(session):
    entry = _note(session, "plain words")
    service.accept_filing(session, entry, True)
    service.accept_filing(session, entry, True)
    assert entry.user_filed is True
    assert service.filing_status(session, entry)["filed_by"] == "user"


def test_a_note_nothing_filed_says_none(session):
    entry = _note(session, "plain words")
    entry.filing_state, entry.ai_confidence = "done", 0
    status = service.filing_status(session, entry)
    assert status["filed_by"] == "none" and status["category"] == manager.UNCATEGORISED


def test_a_title_replaces_the_old_one_and_goes_back_out(session):
    entry = _note(session, "# Old\nbody text")
    service.retitle(session, entry, entry.content, "New", "generated title: New")
    assert entry.content.startswith("# New") and "# Old" not in entry.content
    service.remove_title(session, entry)
    assert entry.content.strip() == "body text"
    service.remove_title(session, entry)
    assert entry.content.strip() == "body text"


def test_extraction_links_its_own_notes_and_skips_unknown_refs(session):
    existing = _note(session, "an older note")
    created, links = service.commit_extraction(
        session,
        [("n1", "first new note", "", []), ("n2", "second new note", "", ["kept"])],
        [("n1", "n2", "same topic"), ("n2", f"existing:{existing.id}", "follows on"), ("n9", "n1", "nobody"), ("n1", "existing:x", "bad")],
        None,
    )
    assert [entry.content for entry in created] == ["first new note", "second new note"]
    assert links == 2
