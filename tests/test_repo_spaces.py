"""The spaces repository's first verbs, against a real session (row 3a)."""

from __future__ import annotations

from tessellate.core.database import Document, Entry, Space
from tessellate.repo import spaces


def test_ids_and_all_list_every_space(session):
    session.add(Space(id="atelier", name="Atelier"))
    session.flush()
    assert "atelier" in spaces.ids(session)
    assert "atelier" in {s.id for s in spaces.all_spaces(session)}


def test_find_is_the_row_or_none(session):
    session.add(Space(id="home", name="Home"))
    session.flush()
    assert spaces.find(session, "home").name == "Home"
    assert spaces.find(session, "nope") is None


def test_counts_read_across_workspaces(session):
    session.add(Space(id="lab", name="Lab"))
    session.flush()
    session.add(Entry(content="a", workspace_id="lab"))
    session.add(Document(title="d", workspace_id="lab"))
    session.flush()
    assert spaces.counts(session, "lab") == {"notes": 1, "documents": 1}
