"""What points at a note, from anywhere in the notebook.

INBOX 246, the owner's second sentence: "I want it to show in notes if they
are attached to or referenced in/by a document, note, whiteboard, or
mindmap." `GET /entries/{id}/references` is that answer.

The two halves are found two different ways and the tests are split the same
way, because the failure modes are different. A board or a map carries a note
as a real row, so that half is exact and its only interesting cases are the
ones about which *kind* of board it is and what happens to a note with no
name. A document or another note carries it as text, so that half can be
wrong in both directions: it can miss a reference that is there, and it can
claim one that is not.
"""

from __future__ import annotations

import pytest


def _note(client, content: str) -> dict:
    return client.post("/entries", json={"content": content}).json()


def _board(client, name: str, board_type: str = "board") -> dict:
    return client.post("/whiteboard/boards", json={"name": name, "type": board_type}).json()


def _place(client, board_id: int, entry_id: int) -> dict:
    return client.post(
        "/whiteboard/nodes", json={"entry_id": entry_id, "board_id": board_id, "x": 10, "y": 20}
    ).json()


def _refs(client, entry_id: int) -> list[dict]:
    return client.get(f"/entries/{entry_id}/references").json()["items"]


def test_a_note_nothing_points_at_has_no_references(client):
    note = _note(client, "The roof quote, on its own with nothing pointing at it")
    assert _refs(client, note["id"]) == []


def test_a_board_that_carries_the_note_is_listed_as_a_board(client):
    note = _note(client, "The roof quote")
    board = _board(client, "House jobs")
    _place(client, board["id"], note["id"])

    rows = _refs(client, note["id"])
    assert [(r["kind"], r["how"]) for r in rows] == [("board", "on it")]
    assert rows[0]["id"] == board["id"]
    assert "House jobs" in rows[0]["label"]


def test_a_mind_map_says_map_rather_than_board(client):
    """The owner asked for both by name, so the row has to tell them apart."""
    note = _note(client, "The roof quote")
    board = _board(client, "The house", board_type="map")
    _place(client, board["id"], note["id"])

    rows = _refs(client, note["id"])
    assert [r["kind"] for r in rows] == ["map"]


def test_one_board_carrying_a_note_twice_is_one_row(client):
    """A note can be on a board more than once; it is still one board."""
    note = _note(client, "The roof quote")
    board = _board(client, "House jobs")
    _place(client, board["id"], note["id"])
    _place(client, board["id"], note["id"])

    assert len(_refs(client, note["id"])) == 1


def test_a_note_with_no_name_still_finds_its_boards(client):
    """The text half needs a label to match on; the board half does not.

    An image-only note, or one that opens with a bare heading marker, has no
    label. It is still on the board it was placed on, and a person looking at
    it should be told so.
    """
    note = _note(client, "#")
    board = _board(client, "House jobs")
    _place(client, board["id"], note["id"])

    rows = _refs(client, note["id"])
    assert [r["kind"] for r in rows] == ["board"]


def test_a_wiki_link_from_another_note_is_a_link_and_a_mention_is_not(client):
    note = _note(client, "The roof quote")
    linked = _note(client, "Chased the roofer, see [[The roof quote]] for the number")
    mentioned = _note(client, "Told mum about The roof quote over dinner")

    rows = {r["id"]: r for r in _refs(client, note["id"])}
    assert rows[linked["id"]]["how"] == "links to it"
    assert rows[mentioned["id"]]["how"] == "mentions it"
    assert rows[linked["id"]]["kind"] == "note"


def test_links_are_listed_before_mentions(client):
    """A link is a decision someone made; a mention is a coincidence until
    they make it, so the rows someone chose come first."""
    note = _note(client, "The roof quote")
    _note(client, "aaa mentions The roof quote")
    _note(client, "zzz links to [[The roof quote]]")

    hows = [r["how"] for r in _refs(client, note["id"])]
    assert hows == ["links to it", "mentions it"], hows


def test_a_document_that_mentions_the_note_is_listed(client):
    note = _note(client, "The roof quote")
    client.post(
        "/documents",
        json={"title": "House plan", "content": "Waiting on [[The roof quote]] before booking."},
    )

    rows = _refs(client, note["id"])
    assert [(r["kind"], r["how"]) for r in rows] == [("document", "links to it")]
    assert rows[0]["label"] == "House plan"


def test_the_note_does_not_reference_itself(client):
    """It contains its own label, so a scan that forgets to exclude it finds
    it every time."""
    note = _note(client, "The roof quote, and later in the note, The roof quote again")
    assert _refs(client, note["id"]) == []


def test_a_deleted_note_is_not_listed_as_a_reference(client):
    note = _note(client, "The roof quote")
    other = _note(client, "Links to [[The roof quote]]")
    client.delete(f"/entries/{other['id']}")

    assert _refs(client, note["id"]) == []


def test_a_missing_note_answers_404(client):
    assert client.get("/entries/999999/references").status_code == 404


def test_a_label_does_not_show_its_wiki_brackets(client):
    """`plain_label` strips markdown links and used to miss wiki ones.

    `[text](url)` needs the `(url)` to match, so `[[a wiki link]]` fell
    through and every chip for a note whose first line links to another note
    read `[[The roof quote]]`, brackets and all. Found here, where four of
    the five source labels are wiki links, but the label is used on every
    note chip in the app.
    """
    note = _note(client, "The roof quote")
    _note(client, "[[The roof quote]] is the first thing on this note")

    rows = _refs(client, note["id"])
    assert rows, "nothing referenced it, so this proves nothing"
    assert all("[[" not in row["label"] for row in rows), rows
    assert rows[0]["label"].startswith("The roof quote is the first thing"), rows[0]["label"]


#: **The counts, for a page of cards at once** (INBOX 246's third gap). A card
#: showed nothing until Connections was opened, so a note on two boards and in
#: three documents looked exactly like a note nothing had touched. The chip
#: row needs one number per kind for every card on screen, in one round trip.
def _counts(client, ids: list[int]) -> dict:
    joined = ",".join(str(i) for i in ids)
    return client.get(f"/entries/reference-counts?ids={joined}").json()["counts"]


def test_counts_come_back_per_note_per_kind_in_one_call(client):
    quote = _note(client, "The roof quote")
    other = _note(client, "Nothing points at this one")
    board = _board(client, "The house")
    a_map = _board(client, "Plans", board_type="map")
    _place(client, board["id"], quote["id"])
    _place(client, a_map["id"], quote["id"])
    _note(client, "See [[The roof quote]] before Friday")

    counts = _counts(client, [quote["id"], other["id"]])
    assert counts[str(quote["id"])] == {"board": 1, "map": 1, "note": 1, "total": 3}
    #: A note nothing points at is present with a zero total, not absent:
    #: absent means "not asked" to the client, and a card must be able to
    #: tell "nothing" from "unknown".
    assert counts[str(other["id"])] == {"total": 0}


def test_the_counts_agree_with_the_referenced_by_row(client):
    """One reader: the chip and the row are the same numbers or the chip is a
    lie about what pressing it will show."""
    quote = _note(client, "The roof quote")
    board = _board(client, "The house")
    _place(client, board["id"], quote["id"])
    _note(client, "Mentions The roof quote in passing")
    rows = _refs(client, quote["id"])
    counts = _counts(client, [quote["id"]])[str(quote["id"])]
    assert counts["total"] == len(rows)
    for kind in {r["kind"] for r in rows}:
        assert counts[kind] == sum(1 for r in rows if r["kind"] == kind)


def test_a_deleted_or_unknown_id_is_absent_rather_than_an_error(client):
    quote = _note(client, "The roof quote")
    gone = _note(client, "Soon deleted")
    client.delete(f"/entries/{gone['id']}")
    counts = _counts(client, [quote["id"], gone["id"], 999_999])
    assert str(quote["id"]) in counts
    assert str(gone["id"]) not in counts
    assert "999999" not in counts


def test_garbage_ids_are_ignored_and_an_empty_list_is_empty(client):
    assert client.get("/entries/reference-counts?ids=").json() == {"counts": {}}
    assert client.get("/entries/reference-counts?ids=a,,%20,-1").json() == {"counts": {}}


def test_the_static_path_is_not_swallowed_by_the_entry_id_route(client):
    """`/{entry_id}/references` is declared with an int id; a static path
    declared after it would 422. This pins the order."""
    response = client.get("/entries/reference-counts?ids=1")
    assert response.status_code == 200


# --- the map's own rows -----------------------------------------------------
#
# A mind map does not place a note as a `WhiteboardNode`; it holds a reference
# node, a `WhiteboardObject` of kind "note" whose `data.ref_id` is the note
# (routes_whiteboard `MAP_REFERENCE_KINDS`). INBOX 246's first gap: the
# Referenced-by row and the Connections dialog read the legacy table only,
# so a note on a map through its own node kind was invisible to both.


def _map_node(client, board_id: int, entry_id: int) -> dict:
    created = client.post(
        f"/whiteboard/boards/{board_id}/nodes",
        json={"kind": "note", "parent_id": None, "text": "", "ref_id": entry_id},
    )
    assert created.status_code == 201, created.text
    return created.json()


def test_a_map_reference_node_is_a_map_reference(client):
    note = _note(client, "The roof quote")
    the_map = _board(client, "The house", board_type="map")
    _map_node(client, the_map["id"], note["id"])

    rows = _refs(client, note["id"])
    assert [(r["kind"], r["id"], r["how"]) for r in rows] == [("map", the_map["id"], "on it")]
    assert "The house" in rows[0]["label"]


def test_a_map_holding_the_note_both_ways_is_one_row(client):
    """A legacy card row and a reference node on the same map is one map."""
    note = _note(client, "The roof quote")
    the_map = _board(client, "The house", board_type="map")
    _place(client, the_map["id"], note["id"])
    _map_node(client, the_map["id"], note["id"])

    assert len(_refs(client, note["id"])) == 1


def test_a_reference_node_for_a_document_with_the_same_id_is_not_a_note_reference(client):
    """Ids are only meaningful with their table: document 1 is not note 1."""
    note = _note(client, "The roof quote")
    doc = client.post("/documents", json={"title": "Roof", "content": "x"}).json()
    the_map = _board(client, "The house", board_type="map")
    created = client.post(
        f"/whiteboard/boards/{the_map['id']}/nodes",
        json={"kind": "document", "parent_id": None, "text": "", "ref_id": doc["id"]},
    )
    assert created.status_code == 201, created.text
    kinds = [r["kind"] for r in _refs(client, note["id"])]
    assert "map" not in kinds


def test_the_counts_see_a_map_reference_node(client):
    note = _note(client, "The roof quote")
    the_map = _board(client, "The house", board_type="map")
    _map_node(client, the_map["id"], note["id"])
    assert _counts(client, [note["id"]])[str(note["id"])] == {"map": 1, "total": 1}


def test_connections_tell_a_map_from_a_board_and_see_reference_nodes(client):
    note = _note(client, "The roof quote")
    board = _board(client, "House jobs")
    the_map = _board(client, "The house", board_type="map")
    _place(client, board["id"], note["id"])
    _map_node(client, the_map["id"], note["id"])

    out = client.get(f"/entries/{note['id']}/connections").json()
    got = sorted((b["kind"], b["title"]) for b in out["boards"])
    assert got == [("board", "House jobs"), ("map", "The house")]
    assert out["total"] == 2


def test_connections_show_what_the_chip_counts(client):
    """The chip on the card is built from `_reference_rows` and opens the
    Connections dialog; a document that links to the note without the note
    being attached, and a note that only mentions it, were counted on the
    chip and missing from the dialog it opened."""
    note = _note(client, "The roof quote")
    client.post("/documents", json={"title": "House plan", "content": "See [[The roof quote]]."})
    mention = _note(client, "Told mum about The roof quote over dinner")

    out = client.get(f"/entries/{note['id']}/connections").json()
    assert [d["title"] for d in out["documents"]] == ["House plan"]
    assert [(r["id"], r["reason"]) for r in out["incoming"]] == [(mention["id"], "Mentions it")]
    counts = _counts(client, [note["id"]])[str(note["id"])]
    assert counts == {"document": 1, "note": 1, "total": 2}
    assert out["total"] == counts["total"]


# --- the counts for a page cost a handful of statements, not four a card ----
#
# Performance pass, 2026-10-03 (INBOX 441, item 6). `GET /entries/reference-
# counts` runs on every unlock for the first sixty cards, and it asked the
# database four questions per card (two board lookups and two LIKE scans, one
# over documents and one over notes): measured on a 500-note notebook, 242
# statements and 172 ms for sixty ids. The cost that matters is the LIKE
# scans, which read every note's text once per card, so it grows with the
# notebook as well as the page. One scan answers the whole page.


def _statement_count(client, path: str) -> int:
    from sqlalchemy import event

    from tessellate.core import deps

    seen: list[str] = []

    def _record(_conn, _cursor, statement, *_args, **_kwargs):
        seen.append(statement)

    engine = deps.get_db().engine
    event.listen(engine, "before_cursor_execute", _record)
    try:
        assert client.get(path).status_code == 200
    finally:
        event.remove(engine, "before_cursor_execute", _record)
    return len(seen)


def test_the_counts_cost_the_same_statements_for_five_cards_and_forty(client):
    notes = [_note(client, f"Distinct label number {i} about the house") for i in range(40)]
    ids = [n["id"] for n in notes]
    small = _statement_count(client, "/entries/reference-counts?ids=" + ",".join(map(str, ids[:5])))
    large = _statement_count(client, "/entries/reference-counts?ids=" + ",".join(map(str, ids)))
    assert large <= small + 2, f"{large} statements for 40 cards against {small} for 5"
    assert large <= 10, f"{large} statements for one page of counts"


def test_a_mention_matches_whatever_the_case_and_a_wildcard_is_only_itself(client):
    """The one scan must keep the per-card scan's semantics: SQLite's LIKE is
    case-insensitive for ASCII, and `%` and `_` in a label are text."""
    plain = _note(client, "The Roof Quote")
    odd = _note(client, "50% off sale")
    decoy = _note(client, "50 percent off sale")
    _note(client, "told them about the roof QUOTE yesterday")
    _note(client, "got the 50% off sale at last")

    counts = _counts(client, [plain["id"], odd["id"], decoy["id"]])
    assert counts[str(plain["id"])] == {"note": 1, "total": 1}
    assert counts[str(odd["id"])] == {"note": 1, "total": 1}
    assert counts[str(decoy["id"])] == {"total": 0}


def test_two_cards_in_one_page_point_at_each_other_and_not_at_themselves(client):
    a = _note(client, "Alpha plan for the garden")
    b = _note(client, "Beta plan, see [[Alpha plan for the garden]]")
    counts = _counts(client, [a["id"], b["id"]])
    assert counts[str(a["id"])] == {"note": 1, "total": 1}
    assert counts[str(b["id"])] == {"total": 0}
    assert _refs(client, a["id"])[0]["how"] == "links to it"


def test_an_archived_document_and_a_deleted_note_are_not_references_in_a_batch(client):
    note = _note(client, "The roof quote")
    doc = client.post("/documents", json={"title": "Old", "content": "The roof quote again"}).json()
    gone = _note(client, "Mentions The roof quote then dies")
    assert client.put(f"/documents/{doc['id']}/archive").status_code == 200
    client.delete(f"/entries/{gone['id']}")
    assert _counts(client, [note["id"]])[str(note["id"])] == {"total": 0}


def test_a_board_page_counts_each_card_on_its_own_boards(client):
    one = _note(client, "Card one")
    two = _note(client, "Card two")
    board = _board(client, "Jobs")
    the_map = _board(client, "Plans", board_type="map")
    _place(client, board["id"], one["id"])
    _place(client, board["id"], two["id"])
    _map_node(client, the_map["id"], two["id"])
    counts = _counts(client, [one["id"], two["id"]])
    assert counts[str(one["id"])] == {"board": 1, "total": 1}
    assert counts[str(two["id"])] == {"board": 1, "map": 1, "total": 2}


def test_a_note_in_another_space_is_not_a_reference_from_this_one(client):
    """The page scan reads column lists, not whole entities; the space filter
    must still reach them, or a note in Uni would count on a Home card."""
    assert client.post("/spaces", json={"name": "Uni"}).json()["id"] == "uni"
    home = {"X-Workspace-ID": "default"}
    uni = {"X-Workspace-ID": "uni"}
    note = client.post("/entries", json={"content": "The roof quote"}, headers=home).json()
    client.post("/entries", json={"content": "Lecture on The roof quote"}, headers=uni)
    counts = client.get(f"/entries/reference-counts?ids={note['id']}", headers=home).json()["counts"]
    assert counts[str(note["id"])] == {"total": 0}


def test_a_long_label_is_found_through_the_index_with_the_scan_semantics(client):
    """ARCH-11 (audit 2026-10-05): a label with an interior word reads only
    the notes the full-text index says hold that phrase, and still finds a
    mention whose case differs, and still skips a note with the words apart.
    A run-on ("biweekly reviews") is no longer a mention: since audit 1029
    N1 a mention is a whole word, so the substring case moved to the next
    test."""
    label = _note(client, "Weekly review of the garden plan")
    _note(client, "notes from our WEEKLY REVIEW OF THE GARDEN PLAN, kept")
    _note(client, "notes from our biweekly review of the garden plans, kept")
    _note(client, "weekly review, of the garden, plan")
    _note(client, "the garden plan and a weekly review of it")
    counts = _counts(client, [label["id"]])
    assert counts[str(label["id"])] == {"note": 1, "total": 1}


def test_interior_phrase_leaves_out_the_edges_and_short_labels():
    from tessellate.api.routes_entries import _interior_phrase

    assert _interior_phrase("Recipe") is None
    assert _interior_phrase("Weekly review") is None
    assert _interior_phrase("Weekly review of it") == '"review of"'
    assert _interior_phrase('a "quoted" b') == '"quoted"'
    assert _interior_phrase('one "two" three four') == '"two"" three"'
    # No ASCII word inside: not sure the index sees a word there at all.
    assert _interior_phrase("a " + chr(0x2014) + " b") is None
    assert _interior_phrase("café crème brûlée") == '"crème"'



@pytest.mark.parametrize(
    ("title", "text", "expected"),
    [
        ("t", "went to the shop at 5 and ate toast", 0),
        ("rem", "the remainder of the day, a reminder", 0),
        ("Friday", "see you on Friday.", 1),
        ("Friday", "fridays are long", 0),
        ("Friday", "FRIDAY drinks", 1),
        ("Roof", "the roofer came", 0),
        ("Roof", "the roof leaks", 1),
        ("t", "see [[t]] for more", 1),
        ("Ops", "Ops is on call", 1),
        ("Ab", "Ab is two letters", 0),
    ],
)
def test_a_mention_is_a_whole_word_with_a_three_character_floor(client, title, text, expected):
    """Audit 1029 N1: a title is mentioned as a word, not as a substring, and
    a one or two letter title is only ever linked, never guessed at."""
    note = _note(client, title)
    _note(client, text)
    counts = _counts(client, [note["id"]])
    assert counts[str(note["id"])].get("note", 0) == expected
    references = client.get(f"/entries/{note['id']}/references").json()["total"]
    assert references == expected
    connections = client.get(f"/entries/{note['id']}/connections").json()
    assert len(connections["incoming"]) == expected
