"""Phrases as filters (CHAT_PLAN section 2, the graph, library and settings
row): the 40-phrase set at 1.0 (`fixtures/composer/filters_1010.json`), the
filters resolved to the right notes, settings searched by what they do with
synonyms, and the graph and Library asking the route rather than reading."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from tessellate.ai import filters
from tessellate.core.database import Category, Entry, EntryLink

ROOT = Path(__file__).resolve().parents[1]
SET = json.loads((ROOT / "tests/fixtures/composer/filters_1010.json").read_text(encoding="utf-8"))
NOW = datetime.fromisoformat(SET["now"])


def _key(items):
    return sorted(json.dumps({k: v for k, v in f.items() if k != "said"}, sort_keys=True) for f in items)


def test_the_forty_phrases_read_at_one():
    missed = []
    for row in SET["rows"]:
        got = filters.read(row["text"], NOW)
        if _key(got["filters"]) != _key(row["filters"]) or got["rest"] != row["rest"]:
            missed.append((row["text"], got))
    assert len(SET["rows"]) == 40
    assert not missed, f"{40 - len(missed)} of 40: {missed}"


def test_the_filters_leave_the_right_notes(session):
    naive = NOW.replace(tzinfo=None)
    work = Category(name="Work")
    session.add(work)
    session.flush()
    hub = Entry(content="Harbor\nThe boat shed plan.", updated_at=naive - timedelta(days=1), created_at=naive - timedelta(days=200))
    old = Entry(content="Crane hire quote", tags='["work"]', category_id=work.id, updated_at=naive - timedelta(days=150),
                created_at=naive - timedelta(days=150))
    fresh = Entry(content="Paint list with Sam", tags='["work"]', pinned=True, updated_at=naive - timedelta(days=2),
                  created_at=naive - timedelta(days=2))
    alone = Entry(content="A lonely thought", updated_at=naive - timedelta(days=3), created_at=naive - timedelta(days=3))
    session.add_all([hub, old, fresh, alone])
    session.flush()
    session.add_all([EntryLink(source_entry_id=hub.id, target_entry_id=old.id), EntryLink(source_entry_id=fresh.id, target_entry_id=hub.id)])
    session.commit()

    def ids(phrase):
        return set(filters.resolve(session, filters.read(phrase, NOW)["filters"], NOW))

    assert ids("connected to Harbor") == {old.id, fresh.id}
    assert ids("connected to Harbor and untouched since June") == {old.id}
    assert ids("tagged work edited last week") == {fresh.id}
    assert ids("connected to nothing") == {alone.id}
    assert ids("pinned") == {fresh.id}
    assert ids("filed under work") == {old.id}
    assert ids("mentioning Sam") == {fresh.id}


def test_the_route_reads_and_resolves(client):
    token = client.post("/auth/setup", json={"password": "first-pass"}).json()["token"]
    got = client.get("/read/filter", params={"q": "pinned", "now": SET["now"]}, headers={"X-Auth-Token": token}).json()
    assert got["filters"][0]["kind"] == "pinned" and got["ids"] == []
    plain = client.get("/read/filter", params={"q": "harbor"}, headers={"X-Auth-Token": token}).json()
    assert plain["filters"] == [] and plain["ids"] is None
    words = client.get("/read/words", headers={"X-Auth-Token": token}).json()["groups"]
    assert ["dark", "night", "theme", "light mode", "dim", "black"] in words


def test_the_surfaces_ask_the_route():
    js = ROOT / "frontend/js"
    assert '"/read/filter?q="' in (js / "graph.js").read_text(encoding="utf-8")
    assert '"/read/filter?q="' in (js / "library.js").read_text(encoding="utf-8")
    #: Every search box's meaning layer (Brief 94), in the Settings bundle.
    assert '"/read/words"' in (js / "meaning.js").read_text(encoding="utf-8")


def test_a_private_note_or_a_board_is_never_a_filter_result(session):
    """Security review 2026-10-19: `resolve` started from not-binned, not-draft
    only, so "tagged work" returned a private note's id by its plaintext tags,
    and boards too. It starts from what the reading tools may see."""
    shown = Entry(content="Crane hire quote", tags='["work"]')
    hidden = Entry(content="Salary talk", tags='["work"]', is_private=True)
    board = Entry(content="Work board", tags='["work"]', is_board=True)
    session.add_all([shown, hidden, board])
    session.commit()
    assert set(filters.resolve(session, filters.read("tagged work", NOW)["filters"], NOW)) == {shown.id}
