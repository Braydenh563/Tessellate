"""What `GET /board-library` returns on the paths the other library tests skip.

Characterisation tests written before `list_library` was split into the
person's items, the marks and recents, and the built-in matches (cc-1101): the
favourites filter, the kind filter against built-ins, the icons that join a
word search and its cap of 200, and the built-in sets file being unreadable.
"""

from __future__ import annotations

from tessellate.api import routes_board_library as library


def _element():
    item = {"key": "t", "kind": "object", "type": "text", "data": {"content": "Hello"}, "x": 0, "y": 0, "w": 120, "h": 40, "z": 1}
    return {"box": {"w": 120, "h": 40}, "items": [item], "links": []}


def _save(client, name, **extra):
    out = client.post("/board-library", json={"kind": "element", "name": name, "payload": _element(), **extra})
    assert out.status_code == 201, out.text
    return out.json()


def test_favourites_lists_only_the_favourite_items(client):
    keep = _save(client, "Kept")
    _save(client, "Left")
    client.put(f"/board-library/{keep['id']}", json={"favourite": True})
    listed = client.get("/board-library?favourites=true").json()
    assert [i["name"] for i in listed["items"]] == ["Kept"]
    assert client.get("/board-library").headers["X-Total-Count"] == "2"
    assert client.get("/board-library?favourites=true").headers["X-Total-Count"] == "1"


def test_a_kind_lists_only_built_ins_of_that_kind(client):
    kinds = {e.get("kind", "element") for e in library._builtin_index().values()}
    assert len(kinds) > 1, "the built-in sets hold more than one kind"
    for kind in sorted(kinds):
        found = client.get(f"/board-library?kind={kind}").json()["builtins"]
        assert found and {b["kind"] for b in found} == {kind}
        assert len(found) <= 200


def test_a_word_search_adds_icons_unless_a_non_element_kind_is_asked_for(client):
    icon = next(iter(library._icons()))
    word = icon.split("-")[0]
    keys = [b["key"] for b in client.get(f"/board-library?q={word}").json()["builtins"]]
    assert f"icons/{icon}" in keys
    icons = [b for b in client.get(f"/board-library?q={word}&kind=element").json()["builtins"] if b["set"] == "Icons"]
    assert icons and all(b["kind"] == "element" for b in icons)
    other = next(k for k in {e.get("kind", "element") for e in library._builtin_index().values()} if k != "element")
    assert not [b for b in client.get(f"/board-library?q={word}&kind={other}").json()["builtins"] if b["set"] == "Icons"]


def test_builtin_matches_are_capped_at_two_hundred(client):
    assert len(library._icons()) > 200
    assert len(client.get("/board-library?q=a").json()["builtins"]) == 200


def test_unreadable_built_in_sets_list_as_empty(client, monkeypatch, tmp_path):
    monkeypatch.setattr(library, "BUILTIN_DIR", tmp_path)
    listed = client.get("/board-library").json()
    assert listed["sets"] == []
