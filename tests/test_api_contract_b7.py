"""The API contract (WORLD_CLASS_PLAN B7): cursors, ETags, `If-Match`, `/capabilities`.

Four promises, each one a client outside the app's own page can rely on:

- every paged list can be walked by following `X-Next-Cursor` until it is
  absent, and `offset` keeps working for the callers that already use it;
- the notes list's cursor is a keyset, so a note saved between two page
  requests neither repeats a row nor hides one;
- a note read carries an `ETag`, and a write that sends `If-Match` with a
  version that is no longer current is refused with 412 and the current note;
- `/capabilities` answers what this install has, behind the unlock.
"""

from __future__ import annotations

import inspect
from datetime import timedelta

from tessellate.api import paging
from tessellate.api.app import create_app
from tessellate.core import deps
from tessellate.core.database import Entry
from tests.test_list_limits import _routes


def _make_notes(client, n: int) -> list[int]:
    ids = []
    for i in range(n):
        r = client.post("/entries", json={"content": f"Note number {i} about cursors"})
        assert r.status_code == 201, r.text
        ids.append(r.json()["id"])
    # Distinct creation times, oldest first, so the order is the ids reversed
    # and does not depend on two saves landing in the same microsecond.
    session = deps.get_db().session()
    try:
        for offset, entry_id in enumerate(ids):
            row = session.get(Entry, entry_id)
            row.created_at = row.created_at - timedelta(minutes=len(ids) - offset)
        session.commit()
    finally:
        session.close()
    return ids


def _walk(client, path: str, limit: int) -> tuple[list[int], int]:
    seen: list[int] = []
    pages = 0
    cursor = None
    while True:
        url = f"{path}?limit={limit}" + (f"&cursor={cursor}" if cursor else "")
        r = client.get(url)
        assert r.status_code == 200, r.text
        seen += [row["id"] for row in r.json()]
        pages += 1
        cursor = r.headers.get(paging.NEXT_CURSOR)
        if not cursor:
            return seen, pages
        assert pages < 50


def test_the_notes_list_walks_by_cursor_in_the_offset_order(client):
    ids = _make_notes(client, 7)
    by_offset = [row["id"] for row in client.get("/entries?limit=100").json()]
    walked, pages = _walk(client, "/entries", 3)
    assert walked == by_offset == list(reversed(ids))
    assert pages == 3


def test_a_note_saved_between_pages_does_not_repeat_a_row(client):
    _make_notes(client, 6)
    first = client.get("/entries?limit=3")
    cursor = first.headers[paging.NEXT_CURSOR]
    # A new note is the newest, so by offset it pushes page one's last row
    # onto page two as well; by keyset it cannot.
    client.post("/entries", json={"content": "Saved while page one was on screen"})
    second = client.get(f"/entries?limit=3&cursor={cursor}").json()
    page_one = {row["id"] for row in first.json()}
    assert not page_one & {row["id"] for row in second}
    assert len(second) == 3


def test_offset_paging_still_works_and_says_the_total(client):
    _make_notes(client, 5)
    r = client.get("/entries?limit=2&offset=2")
    assert r.status_code == 200
    assert len(r.json()) == 2
    assert r.headers["X-Total-Count"] == "5"


def test_a_cursor_that_was_never_given_out_is_a_422(client):
    assert client.get("/entries?cursor=bm90LWEtY3Vyc29y").status_code == 422
    # An offset cursor on the keyset list is the wrong kind, not page one.
    assert client.get(f"/entries?cursor={paging.offset_cursor(3)}").status_code == 422
    assert client.get(f"/reminders?cursor={paging.keyset_cursor((1,))}").status_code == 422


def test_an_offset_paged_list_walks_by_cursor_too(client):
    for i in range(5):
        r = client.post("/bookmarks", json={"url": f"https://example.org/{i}", "title": f"Page {i}"})
        assert r.status_code in (200, 201), r.text
    by_offset = [row["id"] for row in client.get("/bookmarks?limit=100").json()]
    walked, pages = _walk(client, "/bookmarks", 2)
    assert walked == by_offset
    assert pages == 3


def test_every_route_that_pages_by_offset_takes_a_cursor(app_state):
    """The contract is one way to walk every list: a route added with an
    `offset` and no `cursor` would be the one list a client cannot follow."""
    missing = []
    for route, path in _routes(create_app()):
        params = inspect.signature(route.endpoint).parameters
        if "offset" in params and "cursor" not in params:
            missing.append(path)
    assert not missing, f"these lists page by offset but take no cursor: {missing}"


def test_a_note_carries_its_version_as_an_etag(client):
    r = client.post("/entries", json={"content": "Versioned"})
    note = r.json()
    got = client.get(f"/entries/{note['id']}")
    assert got.headers["ETag"] == f'"{got.json()["content_hash"]}"'


def test_if_match_refuses_a_write_made_from_an_old_version(client):
    note = client.post("/entries", json={"content": "First text"}).json()
    etag = client.get(f"/entries/{note['id']}").headers["ETag"]
    # Somebody else (a background AI edit, another window) saves first.
    assert client.put(f"/entries/{note['id']}", json={"content": "Their text"}).status_code == 200
    stale = client.put(
        f"/entries/{note['id']}", json={"tags": ["mine"]}, headers={"If-Match": etag}
    )
    assert stale.status_code == 412
    detail = stale.json()["detail"]
    assert detail["code"] == "precondition_failed"
    assert detail["current"]["content"] == "Their text"
    # Nothing was written by the refused request.
    assert "mine" not in client.get(f"/entries/{note['id']}").json()["tags"]
    # Delete is guarded the same way.
    refused = client.delete(f"/entries/{note['id']}", headers={"If-Match": etag})
    assert refused.status_code == 412


def test_if_match_with_the_current_version_or_a_star_goes_through(client):
    note = client.post("/entries", json={"content": "Current text"}).json()
    etag = client.get(f"/entries/{note['id']}").headers["ETag"]
    r = client.put(
        f"/entries/{note['id']}", json={"content": "Edited"}, headers={"If-Match": etag}
    )
    assert r.status_code == 200
    assert r.headers["ETag"] != etag
    assert (
        client.put(
            f"/entries/{note['id']}", json={"content": "Again"}, headers={"If-Match": "*"}
        ).status_code
        == 200
    )
    # A weak tag never matches, as RFC 9110 says for If-Match.
    weak = "W/" + client.get(f"/entries/{note['id']}").headers["ETag"]
    assert (
        client.put(
            f"/entries/{note['id']}", json={"content": "Weak"}, headers={"If-Match": weak}
        ).status_code
        == 412
    )


def test_capabilities_says_what_is_installed(client):
    r = client.get("/capabilities")
    assert r.status_code == 200
    body = r.json()
    assert body["api"]["version"] == 1
    assert body["api"]["next_cursor_header"] == paging.NEXT_CURSOR
    for feature in ("embeddings", "voice", "ocr", "office_import", "tts", "mcp", "lan"):
        assert feature in body["features"], feature
    assert isinstance(body["features"]["voice"]["installed"], bool)



def test_the_packaged_app_offers_its_own_mcp_flag_not_a_python_command(client, monkeypatch):
    """`python -m tessellate.mcp_server` has no Python to run in behind a
    frozen exe; the packaged app said "installed" with it anyway. It now
    answers with `--mcp`, which the exe does take (OPEN ledger 319)."""
    import sys

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    r = client.get("/capabilities")
    mcp = r.json()["features"]["mcp"]
    assert mcp["installed"] is True and mcp["command"] == "Tessellate --mcp"
    assert mcp["config"]["args"] == ["--mcp"] and "python" not in mcp["config"]["args"]
    assert mcp["config"]["env"]["TESSELLATE_DATA_DIR"]
    monkeypatch.delattr(sys, "frozen")
    r2 = client.get("/capabilities")
    source = r2.json()["features"]["mcp"]
    assert source["installed"] is True and source["command"] == "python -m tessellate.mcp_server"
    assert source["config"]["args"] == ["-m", "tessellate.mcp_server"]
    assert source["config"]["env"]["TESSELLATE_DATA_DIR"]


# L-world-class-10: the page hides a control whose backend /capabilities says is not installed.
def test_the_document_importer_is_hidden_when_capabilities_says_markitdown_is_missing():
    from pathlib import Path

    js = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "settings-controls.js").read_text(encoding="utf-8")
    block = js.split('apiJson("/capabilities", { silent: true })', 1)[1].split("});", 1)[0]
    #: Only an explicit false hides it: a failed read must leave the importer where it was.
    assert "office_import?.installed === false" in block
    assert '$("import-document").closest(".fold-help-wrap")' in block and 'classList.add("hidden")' in block
    assert ".catch(() => {})" in js.split('apiJson("/capabilities", { silent: true })', 1)[1][:500]
