"""Notes as a read-only table (a document's ```base block; DOCUMENTS_PLAN gap row 6)."""

from __future__ import annotations


def _note(client, text: str) -> int:
    return client.post("/entries", json={"content": text}).json()["id"]


def _seed(client) -> dict[str, int]:
    return {
        "a": _note(client, "---\ntype: Book\nauthor: Ann\nrating: 9\nstatus: read\n---\n# Alpha book"),
        "b": _note(client, "---\ntype: Book\nauthor: Ben\nrating: 10\nstatus: unread\ntags: [x, y]\n---\n# Beta book"),
        "c": _note(client, "---\ntype: Movie\nauthor: Ann\nrating: 3\n---\n# Gamma movie"),
        "d": _note(client, "A note with no properties at all."),
    }


def test_a_type_and_its_columns_come_back_as_rows(client) -> None:
    ids = _seed(client)
    got = client.get("/property-table", params={"type": "book", "columns": "author, rating, status"}).json()
    assert got["total"] == 2 and got["columns"] == ["author", "rating", "status"]
    by_id = {r["id"]: r for r in got["rows"]}
    assert set(by_id) == {ids["a"], ids["b"]}
    assert by_id[ids["a"]]["title"] == "Alpha book"
    assert by_id[ids["a"]]["values"] == {"author": ["Ann"], "rating": ["9"], "status": ["read"]}


def test_conditions_all_hold_and_a_list_matches_any_value(client) -> None:
    ids = _seed(client)
    only = client.get("/property-table", params={"where": ["author=ann", "rating=3"], "columns": "author"}).json()
    assert [r["id"] for r in only["rows"]] == [ids["c"]]
    tagged = client.get("/property-table", params={"where": "tags=y"}).json()
    assert [r["id"] for r in tagged["rows"]] == [ids["b"]]


def test_sort_reads_numbers_as_numbers_and_puts_the_unset_last(client) -> None:
    ids = _seed(client)
    asc = client.get("/property-table", params={"type": "Book", "sort": "rating"}).json()
    assert [r["id"] for r in asc["rows"]] == [ids["a"], ids["b"]]  # 9 before 10, not "10" before "9"
    desc = client.get("/property-table", params={"columns": "rating", "sort": "rating", "desc": "true"}).json()
    assert [r["id"] for r in desc["rows"]][:3] == [ids["b"], ids["a"], ids["c"]]
    unset = client.get("/property-table", params={"type": "Book", "sort": "status", "desc": "true"}).json()
    assert [r["id"] for r in unset["rows"]] == [ids["b"], ids["a"]]


def test_limit_trims_the_rows_not_the_total(client) -> None:
    _seed(client)
    got = client.get("/property-table", params={"type": "Book", "limit": 1}).json()
    assert got["total"] == 2 and len(got["rows"]) == 1


def test_a_query_with_nothing_in_it_and_a_bad_condition_are_refused(client) -> None:
    assert client.get("/property-table").status_code == 422
    assert client.get("/property-table", params={"where": "no equals sign"}).status_code == 422


def test_a_deleted_note_is_not_in_the_table(client) -> None:
    ids = _seed(client)
    client.delete(f"/entries/{ids['a']}")
    got = client.get("/property-table", params={"type": "Book"}).json()
    assert [r["id"] for r in got["rows"]] == [ids["b"]]
