"""The kinds-of-link repository's verbs, against a real session (INBOX 1499).

`test_relation_types_kg3.py` holds the routes unchanged; these hold the
repository's contract: one cached read of every kind per session, writes that
flush and drop the cache but leave the commit to the caller, and the
whole-notebook retype on delete and restore.
"""

from __future__ import annotations

import pytest

from tessellate.core.database import Entry, EntryLink
from tessellate.repo import Conflict, Invalid, NotFound, ReadOnly, relation_types


def test_kinds_lists_the_built_ins_then_custom_ones_and_caches(session):
    kinds = relation_types.kinds(session)
    assert kinds["supports"]["built_in"] is True
    assert relation_types.kinds(session) is kinds
    made = relation_types.create(session, name=" Part   of ", inverse="Has part")
    assert made["key"] == "part_of" and made["name"] == "Part of" and made["built_in"] is False
    assert relation_types.kinds(session) is not kinds


def test_create_refuses_a_blank_name_a_twin_and_a_bad_colour(session):
    with pytest.raises(Invalid):
        relation_types.create(session, name="  ")
    relation_types.create(session, name="Cites")
    with pytest.raises(Conflict):
        relation_types.create(session, name="cites")
    with pytest.raises(Conflict):
        relation_types.create(session, name="Supports")
    with pytest.raises(Invalid):
        relation_types.create(session, name="Tinted", colour="not a colour!")


def test_update_changes_only_sent_fields_and_built_ins_are_read_only(session):
    relation_types.create(session, name="Part of", inverse="Has part", colour="teal")
    changed = relation_types.update(session, "part_of", {"inverse": "Contains"})
    assert (changed["name"], changed["inverse"], changed["colour"]) == ("Part of", "Contains", "teal")
    with pytest.raises(ReadOnly):
        relation_types.update(session, "supports", {"inverse": "x"})
    with pytest.raises(NotFound):
        relation_types.update(session, "nothing_here", {"inverse": "x"})


def test_delete_untypes_its_links_and_a_restore_puts_them_back(session):
    a, b = Entry(content="A"), Entry(content="B")
    session.add_all([a, b])
    session.flush()
    relation_types.create(session, name="Cites")
    link = EntryLink(source_entry_id=a.id, target_entry_id=b.id, link_type="cites")
    session.add(link)
    session.flush()
    untyped, restore = relation_types.delete(session, "cites")
    session.refresh(link)
    assert untyped == 1 and link.link_type is None and restore["link_ids"] == [link.id]
    assert "cites" not in relation_types.kinds(session)
    relation_types.create(session, name=restore["name"], key=restore["key"], link_ids=restore["link_ids"])
    session.refresh(link)
    assert link.link_type == "cites"


def test_a_write_leaves_the_commit_to_its_caller(session):
    relation_types.create(session, name="Part of")
    session.rollback()
    relation_types.forget(session)
    assert "part_of" not in relation_types.kinds(session)
