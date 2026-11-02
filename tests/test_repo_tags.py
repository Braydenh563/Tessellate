"""The tags repository's verbs, against a real session (INBOX 1499).

`test_tag_manager_routes.py` holds the routes unchanged; these hold the
repository's contract: a cached count, a page cut that keeps the most used,
and writes that flush and leave the commit to the caller.
"""

from __future__ import annotations

import json

import pytest
from sqlalchemy import select

from tessellate.core.database import Entry
from tessellate.repo import NotFound, tags


@pytest.fixture(autouse=True)
def _fresh_cache():
    tags.reset_tag_cache()
    yield
    tags.reset_tag_cache()


def _note(session, *names: str) -> Entry:
    entry = Entry(content="n", tags=json.dumps(list(names)))
    session.add(entry)
    session.flush()
    return entry


def _has(session, entry: Entry) -> list[str]:
    session.refresh(entry)
    return json.loads(entry.tags)


def test_counts_find_get_and_page_read_the_same_numbers(session):
    _note(session, "gym", "food")
    _note(session, "gym")
    _note(session, "gym", "trip")
    assert list(tags.counts(session).items())[0] == ("gym", 3)
    assert tags.find(session, "food") == 1 and tags.find(session, "nope") is None
    assert tags.get(session, "gym") == 3
    with pytest.raises(NotFound):
        tags.get(session, "nope")
    cut, total = tags.page(session, limit=2)
    assert list(cut) == ["gym", "food"] and total == 3
    whole, total = tags.page(session, limit=10)
    assert whole == tags.counts(session) and total == 3


def test_rename_merges_flushes_and_leaves_the_commit_to_the_caller(session):
    a, b = _note(session, "run"), _note(session, "fitness", "run")
    session.commit()
    before = tags.rename(session, ["run"], "fitness")
    assert before == {a.id: ["run"], b.id: ["fitness", "run"]}
    assert _has(session, a) == ["fitness"] and _has(session, b) == ["fitness"]
    session.rollback()
    assert _has(session, a) == ["run"], "the repository must not have committed"


def test_rename_refuses_a_blank_name_and_a_comma(session):
    _note(session, "a")
    with pytest.raises(ValueError):
        tags.rename(session, ["a"], "   ")
    with pytest.raises(ValueError):
        tags.rename(session, ["a"], "x, y")


def test_remove_and_restore_are_each_others_undo(session):
    a, b = _note(session, "x", "keep"), _note(session, "y")
    before = tags.remove(session, ["x"])
    assert before == {a.id: ["x", "keep"]} and _has(session, a) == ["keep"] and _has(session, b) == ["y"]
    tags.restore(session, before)
    assert _has(session, a) == ["x", "keep"]


def test_bulk_edit_adds_after_removing_case_insensitively_and_skips_the_binned(session):
    live, binned = _note(session, "Food"), _note(session, "food")
    binned.is_deleted = True
    session.flush()
    before = tags.bulk_edit(session, [live.id, binned.id], add=["dinner"], remove=["food"])
    assert list(before) == [live.id] and _has(session, live) == ["dinner"]
    assert tags.bulk_edit(session, [], ["a"], []) == {}


def test_remove_from_touches_only_the_named_notes(session):
    a, b = _note(session, "Old", "k"), _note(session, "old")
    before = tags.remove_from(session, {a.id: {"old"}})
    assert before == {a.id: ["Old", "k"]} and _has(session, a) == ["k"] and _has(session, b) == ["old"]


def test_tagged_skips_private_untagged_and_binned_notes(session):
    a = _note(session, "grocery list")
    _note(session)
    private = _note(session, "grocery")
    private.is_private = True
    binned = _note(session, "grocery")
    binned.is_deleted = True
    session.flush()
    assert tags.tagged(session, limit=10) == [(a.id, ["grocery list"])]


def test_mentioning_matches_anywhere_or_only_the_start_of_a_tag(session):
    a = _note(session, "grocery list")
    anywhere = list(session.scalars(select(Entry.id).where(*tags.mentioning(["list"]))))
    at_start = list(session.scalars(select(Entry.id).where(*tags.mentioning(["list"], whole_start=True))))
    plural = list(session.scalars(select(Entry.id).where(*tags.mentioning(["grocerys"], whole_start=True))))
    assert anywhere == [a.id] and at_start == [] and plural == [a.id]
