"""The search box (WORLD_CLASS_PLAN decision 46, phase 25a, Brief 47).

One box, every kind: the operators it documents are read by
`search/query.py` (the one reader, `tests/test_one_reader.py`) and answered
by the engine, and the route hands back one result list with a `kind` on
every row, paged like the other list routes.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime
from pathlib import Path

import pytest
from sqlalchemy import text as sa_text

from tessellate.core import deps
from tessellate.search.query import understand

NOW = date(2026, 6, 3)



# --- the operators, as the box's help names them ------------------------------


def test_tag_lifts_out_of_the_words():
    u = understand("tag:recipes soup", now=NOW)
    assert u.filters["tag"] == ["recipes"]
    assert u.subject == "soup"


def test_in_names_a_space():
    u = understand("in:work budget", now=NOW)
    assert u.filters["space"] == ["work"]
    assert "in:" not in u.subject


def test_before_and_after_are_dates_not_words():
    u = understand("before:2026-02-01 after:2026-01", now=NOW)
    assert u.until == date(2026, 1, 31)
    assert u.since == date(2026, 1, 2)
    assert u.subject.strip() == ""


def test_has_and_is_are_flags():
    u = understand("has:image is:pinned garden", now=NOW)
    assert u.filters["has"] == ["image"]
    assert u.filters["is"] == ["pinned"]
    assert "garden" in u.subject


def test_quotes_are_a_phrase_and_the_words_stay():
    u = understand('"sourdough starter" feeding', now=NOW)
    assert u.phrases == ["sourdough starter"]
    assert "sourdough" in u.subject


def test_minus_leaves_a_word_out():
    u = understand("risotto -rice", now=NOW)
    assert u.excluded == ["rice"]
    assert "rice" not in u.subject.split()


def test_a_hyphenated_word_is_not_an_exclusion():
    assert understand("state-of-the-art", now=NOW).excluded == []


def test_kind_names_the_chat_kind():
    assert understand("kind:chat budget", now=NOW).filters["kind"] == ["chat"]


# --- the route: one list, every kind, paged -----------------------------------


def _seed_one_of_each():
    from tessellate.core.database import (
        AskTurn,
        Attachment,
        Bookmark,
        Conversation,
        Document,
        Entry,
        Reminder,
    )

    with deps.get_db().session() as session:
        note = Entry(content="zanzibar note about spice")
        session.add(note)
        session.add(Entry(content="zanzibar board", is_board=True))
        session.add(Entry(content="zanzibar map", is_board=True, board_settings=json.dumps({"type": "map"})))
        session.add(Document(title="zanzibar document", content="the document body"))
        session.add(Bookmark(url="https://example.com/z", title="zanzibar bookmark"))
        session.add(Reminder(text="zanzibar reminder", due_at=datetime(2026, 1, 1)))
        session.add(
            Conversation(
                title="Trip chat",
                messages=json.dumps(
                    [
                        {"role": "user", "content": "what should I pack for zanzibar"},
                        {"role": "assistant", "content": "light clothes"},
                    ]
                ),
            )
        )
        session.add(AskTurn(question="when is zanzibar warm", answer="all year"))
        session.flush()
        session.add(Attachment(entry_id=note.id, filename="zanzibar.pdf", stored_name="z1", ocr_text="ferry"))
        session.commit()


def test_every_kind_has_a_count_and_chat_is_one(client):
    body = client.get("/search?q=anything").json()
    from tessellate.search import index

    assert "chat" in index.KINDS
    assert set(body["counts"]) == set(index.KINDS)


def test_one_of_each_kind_is_found_by_one_query(client):
    _seed_one_of_each()
    body = client.get("/search?q=zanzibar&limit=50&hybrid=false").json()
    kinds = {hit["kind"] for hit in body["hits"]}
    assert kinds >= {"note", "document", "board", "map", "file", "bookmark", "reminder", "chat"}
    for hit in body["hits"]:
        assert {"kind", "id", "source", "title", "snippet", "written"} <= set(hit)


def test_a_chat_turn_and_an_ask_turn_are_both_chat(client):
    _seed_one_of_each()
    hits = client.get("/search?q=zanzibar&kind=chat&hybrid=false").json()["hits"]
    assert {hit["source"] for hit in hits} == {"conversations", "ask_turns"}
    assert {hit["kind"] for hit in hits} == {"chat"}


def test_the_route_pages(client):
    with deps.get_db().session() as session:
        from tessellate.core.database import Entry

        for index in range(7):
            session.add(Entry(content=f"paging marmalade {index}"))
        session.commit()
    first = client.get("/search?q=marmalade&limit=3&page=1&hybrid=false").json()
    second = client.get("/search?q=marmalade&limit=3&page=2&hybrid=false").json()
    third = client.get("/search?q=marmalade&limit=3&page=3&hybrid=false").json()
    assert (first["page"], first["limit"]) == (1, 3)
    assert len(first["hits"]) == 3 and first["more"] is True
    assert len(second["hits"]) == 3 and second["more"] is True
    assert len(third["hits"]) == 1 and third["more"] is False
    ids = [hit["id"] for page in (first, second, third) for hit in page["hits"]]
    assert len(set(ids)) == 7


def test_limit_and_page_are_bounded(client):
    answer = client.get("/search?q=x&limit=500")
    assert answer.status_code == 422
    answer = client.get("/search?q=x&page=0")
    assert answer.status_code == 422


def test_a_chat_already_written_is_indexed_at_the_next_start(app_state):
    """A notebook indexed before chats were a kind: the boot reconcile adds them."""
    from tessellate.core.database import Conversation
    from tessellate.search import index

    with deps.get_db().session() as session:
        session.add(Conversation(title="old", messages=json.dumps([{"role": "user", "content": "quokka"}])))
        session.commit()
        session.execute(sa_text("DELETE FROM search_index WHERE kind = 'chat'"))
        session.commit()
        assert index.counts(session)["chat"] == 0
        assert index.reconcile_sources(session) is True
        session.commit()
        assert index.counts(session)["chat"] == 1
        assert index.reconcile_sources(session) is False


def test_a_deleted_conversation_leaves_the_index(client):
    from tessellate.core.database import Conversation

    with deps.get_db().session() as session:
        conv = Conversation(title="gone", messages=json.dumps([{"role": "user", "content": "axolotl"}]))
        session.add(conv)
        session.commit()
        session.delete(conv)
        session.commit()
    answer = client.get("/search?q=axolotl&hybrid=false")
    assert answer.json()["hits"] == []


@pytest.mark.parametrize("q", ['tag:"two words"', "in:", "before:", "-", '"'])
def test_a_ragged_box_never_errors(client, q):
    answer = client.get("/search", params={"q": q})
    assert answer.status_code == 200


# --- the box: lazy, keyboard, help, saved searches ----------------------------

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"


def _text(name: str) -> str:
    return (JS / name).read_text(encoding="utf-8")


def test_the_box_is_lazy_and_opened_through_a_stand_in():
    app = _text("app.js")
    assert 'search: ["/css/search-lazy.css", "/js/search.js"]' in app
    entry = re.search(r"search: \[([^\]]*)\],\n", app[app.index("const LAZY_ENTRY_POINTS") :])
    assert entry and '"openFinder"' in entry.group(1)
    index = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert "/js/search.js" not in index and "search-lazy.css" not in index
    for name in ("spaces-find.js", "wiring.js", "app.js"):
        assert "function openFinder(" not in _text(name), name
    assert "function openFinder(" in _text("search.js")


def test_every_kind_the_index_holds_has_a_chip_and_an_opener():
    from tessellate.search import index

    source = _text("search.js")
    kinds = source[source.index("const FINDER_KINDS = [") :]
    kinds = kinds[: kinds.index("];")]
    opens = source[source.index("const FINDER_OPEN = {") :]
    opens = opens[: opens.index("\n};")]
    for kind in index.KINDS:
        assert f'key: "{kind}"' in kinds, kind
        if kind != "file":
            assert re.search(rf"\b{kind}: ", opens), kind
    assert '"tag finder-kind"' in source


def test_the_keys_are_arrows_enter_and_escape():
    source = _text("search.js")
    wire = source[source.index("function wireFinder()") :]
    for key in ('"ArrowDown"', '"ArrowUp"', '"Enter"', '"Escape"'):
        assert key in wire, key


def test_the_help_names_every_operator():
    index = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    help_body = index[index.index('id="finder-help"') :]
    help_body = help_body[: help_body.index("</div>")]
    for op in ("tag:", "in:", "kind:", "before:", "after:", "has:", "is:", "&quot;exact phrase&quot;" if "&quot;" in help_body else '"exact phrase"', "-word"):
        assert op in help_body, op


def test_saved_searches_are_kept_in_preferences(client):
    saved = [{"name": "Ink", "query": "tag:ink quill"}]
    answer = client.put("/preferences", json={"saved_finds": saved})
    assert answer.status_code == 200
    answer = client.get("/preferences")
    assert answer.json()["saved_finds"] == saved
    answer = client.put("/preferences", json={"saved_finds": [{"name": "", "query": "x"}]})
    assert answer.status_code == 422


def test_a_tag_alone_finds_every_note_it_is_on_not_the_newest_page(client):
    """`tag:` was applied after the newest 200 rows were read, so an older
    tagged note was never found by the tag alone (Brief 47's bench)."""
    from tessellate.core.database import Entry

    with deps.get_db().session() as session:
        for index in range(3):
            session.add(Entry(content=f"old tagged {index}", tags=json.dumps(["rarebird"]), created_at=datetime(2020, 1, 1)))
        for index in range(230):
            session.add(Entry(content=f"newer plain {index}", created_at=datetime(2026, 1, 1)))
        session.commit()
    answer = client.get("/search?q=tag:rarebird&limit=50&hybrid=false")
    assert len(answer.json()["hits"]) == 3


def test_search_rows_of_a_private_notes_files_are_removed_at_the_next_start(app_state):
    """SEC-A2: rows indexed before files of private notes were left out are cleared once."""
    from tessellate.core.database import Attachment, Entry
    from tessellate.search import index

    with deps.get_db().session() as session:
        private = Entry(content="p", is_private=True)
        plain = Entry(content="q")
        session.add_all([private, plain])
        session.flush()
        hidden = Attachment(entry_id=private.id, filename="hid.txt", stored_name="h1", mime="text/plain", size=1)
        shown = Attachment(entry_id=plain.id, filename="shown.txt", stored_name="s1", mime="text/plain", size=1)
        session.add_all([hidden, shown])
        session.commit()
        source = index.source_for("attachments")
        index._write(session.connection(), source, hidden.id, index.Row(title="hid.txt", body="LEAKWORD"))
        index._write(session.connection(), source, shown.id, index.Row(title="shown.txt", body="fine"))
        session.commit()
        assert index.reconcile_private_files(session) is True
        session.commit()
        assert index.reconcile_private_files(session) is False
        left = [r[0] for r in session.execute(sa_text("SELECT title FROM search_index WHERE kind = 'file'")).all()]
        assert "hid.txt" not in left and "shown.txt" in left
