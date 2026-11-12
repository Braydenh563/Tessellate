"""Merge and remove for graph topics, saved as overrides (ledger L711).

Topics are recomputed from the links, so a merge or a removal is stored by the
notes it covers and laid over the worked-out topics; a reset brings the
automatic grouping back. Renames stay a separate, older layer.
"""

from __future__ import annotations

from tessellate.entry import topics


def _topic(tid, ids, name, terms=()):
    return {"id": tid, "size": len(ids), "name": name, "terms": list(terms), "ids": ids, "core_id": ids[0]}


FOUND = [_topic(0, [1, 2, 3, 4, 5], "#glaze"), _topic(1, [6, 7, 8], "#kiln"), _topic(2, [9, 10, 11], "#garden")]


def test_no_edits_changes_nothing():
    assert topics.apply_edits(FOUND, {}) == FOUND


def test_a_merge_joins_the_topics_it_covers_and_keeps_the_biggest_name():
    edits = topics.store_merge({}, [1, 2, 3, 4, 5, 6, 7, 8])
    out = topics.apply_edits(FOUND, edits)
    assert [t["name"] for t in out] == ["#glaze", "#garden"]
    assert out[0]["ids"] == [1, 2, 3, 4, 5, 6, 7, 8] and out[0]["size"] == 8
    assert out[0]["merged"] is True
    assert [t["id"] for t in out] == [0, 1], "ids are positions again"
    assert FOUND[0]["size"] == 5, "the cached value is not changed"


def test_a_merge_of_one_topic_does_nothing():
    out = topics.apply_edits(FOUND, topics.store_merge({}, [1, 2, 3, 4, 5]))
    assert [t["ids"] for t in out] == [t["ids"] for t in FOUND]


def test_a_merge_follows_a_topic_that_gained_a_note():
    edits = topics.store_merge({}, [1, 2, 3, 4, 5, 6, 7, 8])
    grown = [_topic(0, [1, 2, 3, 4, 5, 12], "#glaze"), _topic(1, [6, 7, 8], "#kiln")]
    assert topics.apply_edits(grown, edits)[0]["size"] == 9


def test_merging_again_folds_into_the_stored_merge():
    edits = topics.store_merge({}, [1, 2, 3, 4, 5, 6, 7, 8])
    edits = topics.store_merge(edits, [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11])
    assert len(edits["merges"]) == 1
    assert [t["size"] for t in topics.apply_edits(FOUND, edits)] == [11]


def test_a_removal_takes_its_notes_out_and_the_topic_with_them():
    edits = topics.store_remove({}, [6, 7, 8])
    out = topics.apply_edits(FOUND, edits)
    assert [t["name"] for t in out] == ["#glaze", "#garden"]
    assert [t["id"] for t in out] == [0, 1]


def test_a_topic_left_with_two_notes_is_no_topic():
    out = topics.apply_edits(FOUND, topics.store_remove({}, [1, 2, 3]))
    assert [t["name"] for t in out] == ["#kiln", "#garden"]


def test_topic_of_reads_the_edited_topics():
    edits = topics.store_merge({}, [1, 2, 3, 4, 5, 6, 7, 8])
    assert topics.topic_of(topics.apply_edits(FOUND, edits))["7"] == 0


def test_clean_edits_drops_junk_and_caps():
    cleaned = topics.clean_edits({"merges": [[1, "x", 2], []], "excluded": [3, 3, "y"], "extra": 1})
    assert cleaned == {"merges": [[1, 2]], "excluded": [3]}
    assert topics.clean_edits(None) == {"merges": [], "excluded": []}


def _group(client, word, n=4):
    notes = [client.post("/entries", json={"content": f"{word} note {i}", "tags": [word]}).json() for i in range(n)]
    for i, a in enumerate(notes):
        for b in notes[i + 1 :]:
            client.post(f"/entries/{a['id']}/links", json={"target_id": b["id"]})
    return [n["id"] for n in notes]


def test_merge_remove_and_reset_through_the_api(client):
    one, two = _group(client, "glazing"), _group(client, "gardening")
    shown = client.get("/graph/structure?topics=1").json()
    assert len(shown["topics"]) == 2 and shown["topic_edits"] == {"merges": 0, "removed": 0}

    merged = client.post("/graph/topics/merge", json={"ids": one + two})
    assert merged.status_code == 200 and merged.json()["was"] == {"merges": [], "excluded": []}
    shown = client.get("/graph/structure?topics=1").json()
    assert [t["size"] for t in shown["topics"]] == [8] and shown["topics"][0]["merged"]
    assert shown["topic_edits"] == {"merges": 1, "removed": 0}
    of = client.get(f"/graph/topics/of?ids={one[0]},{two[0]}").json()["topics"]
    assert of[str(one[0])]["id"] == of[str(two[0])]["id"] and of[str(one[0])]["size"] == 8

    #: Undo is the same PUT with the old state.
    client.put("/graph/topics/edits", json=merged.json()["was"])
    assert len(client.get("/graph/structure?topics=1").json()["topics"]) == 2

    removed = client.post("/graph/topics/remove", json={"ids": two})
    assert removed.status_code == 200
    shown = client.get("/graph/structure?topics=1").json()
    assert len(shown["topics"]) == 1 and shown["topic_edits"]["removed"] == 4
    assert client.get(f"/graph/topics/of?ids={two[0]}").json() == {"topics": {}}

    client.put("/graph/topics/edits", json={"merges": [], "excluded": []})
    shown = client.get("/graph/structure?topics=1").json()
    assert len(shown["topics"]) == 2 and shown["topic_edits"] == {"merges": 0, "removed": 0}


def test_edits_reject_an_empty_or_huge_list(client):
    empty = client.post("/graph/topics/merge", json={"ids": []})
    huge = client.post("/graph/topics/remove", json={"ids": list(range(5001))})
    assert (empty.status_code, huge.status_code) == (422, 422)



def test_a_topic_says_the_category_most_of_its_notes_sit_in():
    cats = {"1": "Pottery", "2": "Pottery", "3": "Pottery", "4": "Garden", "6": "Garden"}
    out = topics.with_categories(FOUND, cats)
    assert out[0]["category"] == {"name": "Pottery", "count": 3}
    assert "category" not in out[1], "one of three is under half"
    assert "category" not in FOUND[0], "the cached value is not changed"


def test_the_category_shows_on_the_topic(client):
    one, two = _group(client, "glazing"), _group(client, "gardening")
    for note in one:
        client.put(f"/entries/{note}", json={"category": "Pottery"})
    shown = client.get("/graph/structure?topics=1").json()["topics"]
    by_ids = {frozenset(t["ids"]): t for t in shown}
    assert by_ids[frozenset(one)]["category"] == {"name": "Pottery", "count": 4}
    assert "category" not in by_ids[frozenset(two)], "Uncategorised is no category"
