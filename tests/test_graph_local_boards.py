"""L-graph-8: `/graph/local` walks boards only with the Maps switch on, as `/graph` does.

Before, focus mode and the note pane walked every board as a note, so a board
holding two notes joined them in a neighbourhood the map itself drew apart.
"""
from __future__ import annotations

from tessellate.api import routes_graph
from tessellate.core.database import Entry, EntryLink

ROOT_JS = "frontend/js/graph.js"


def _notebook(session):
    a, b = Entry(content="# Alpha"), Entry(content="# Beta")
    board = Entry(content="# My map", is_board=True)
    session.add_all([a, b, board])
    session.flush()
    session.add_all(EntryLink(source_entry_id=board.id, target_entry_id=t) for t in (a.id, b.id))
    session.commit()
    return a.id, b.id, board.id


def _ids(client, url):
    return {n["id"] for n in client.get(url).json()["nodes"]}


def test_a_board_is_left_out_of_the_local_walk_unless_maps_is_on(client, session):
    a, b, board = _notebook(session)
    routes_graph.reset_graph_cache()
    assert _ids(client, f"/graph/local/{a}?depth=2") == {a}
    assert _ids(client, f"/graph/local/{a}?depth=2&include_maps=true") == {a, b, board}
    # Focus on the board itself still draws it and what it holds.
    assert _ids(client, f"/graph/local/{board}?depth=1") == {a, b, board}


def test_both_local_surfaces_send_the_maps_switch():
    from pathlib import Path

    js = (Path(__file__).resolve().parent.parent / ROOT_JS).read_text(encoding="utf-8")
    body = js[js.index("function graphLocalQuery") :]
    body = body[: body.index("\n}\n")]
    assert 'include_maps=${Boolean(document.getElementById("graph-maps")?.checked)}' in body
