"""Topics inside an island, named (GRAPH_PLAN KG6, INBOX 528).

`paths.clusters` stays what it was decided to be: connected components,
exactly true. A big component is often two or three subjects joined by one
bridge, and a reader wants those named. `entry/topics.py` finds them by
weighted label propagation (an edge counts more when its two notes share
neighbours, so a lone bridge cannot pull one subject into another) and names
each by the tags, entities and title words its notes share more than the
notebook does.
"""

from __future__ import annotations

import random
import time
from types import SimpleNamespace

from tessellate.entry import paths, topics


def _index(n, edges):
    index = paths.Connections([SimpleNamespace(id=i) for i in range(1, n + 1)])
    for a, b in edges:
        index._add(a, b, "link", "linked to", "linked to", paths.LINK_WEIGHT)
    return index


def _clique(ids):
    return [(a, b) for i, a in enumerate(ids) for b in ids[i + 1 :]]


def test_two_subjects_joined_by_one_bridge_are_two_topics():
    index = _index(10, _clique([1, 2, 3, 4, 5]) + _clique([6, 7, 8, 9, 10]) + [(5, 6)])
    assert len(paths.clusters(index)) == 1, "one island, as components say"
    labels = topics.detect(index)
    assert len({labels[i] for i in (1, 2, 3, 4, 5)}) == 1
    assert len({labels[i] for i in (6, 7, 8, 9, 10)}) == 1
    assert labels[1] != labels[6]


def test_detection_is_deterministic():
    edges = _clique([1, 2, 3, 4]) + _clique([5, 6, 7, 8]) + [(4, 5), (2, 7)]
    assert topics.detect(_index(8, edges)) == topics.detect(_index(8, edges))


def test_names_come_from_what_the_topic_shares_more_than_the_notebook():
    index = _index(10, _clique([1, 2, 3, 4, 5]) + _clique([6, 7, 8, 9, 10]) + [(5, 6)])
    terms = {i: {("tag", "glaze"), ("tag", "studio")} for i in range(1, 6)}
    terms.update({i: {("tag", "garden"), ("tag", "studio")} for i in range(6, 11)})
    found = topics.build(index, terms)
    names = sorted(t["name"] for t in found)
    assert names == ["#garden", "#glaze"], names
    glaze = next(t for t in found if t["name"] == "#glaze")
    assert glaze["terms"][0] == {"term": "#glaze", "kind": "tag", "notes": 5}
    assert sorted(glaze["ids"]) == [1, 2, 3, 4, 5]


def test_a_pair_is_not_a_topic():
    index = _index(5, _clique([1, 2, 3]) + [(4, 5)])
    found = topics.build(index, {})
    assert [sorted(t["ids"]) for t in found] == [[1, 2, 3]]
    assert found[0]["name"] == "Topic 1", "no shared term: a plain name, never an invented one"


def test_cost_at_10k_notes():
    rng = random.Random(3)
    edges = []
    for start in range(1, 10001, 25):
        group = list(range(start, start + 25))
        edges += [(rng.choice(group), rng.choice(group)) for _ in range(60)]
    edges += [(rng.randrange(1, 10001), rng.randrange(1, 10001)) for _ in range(800)]
    index = _index(10000, [(a, b) for a, b in edges if a != b])
    started = time.process_time()
    found = topics.build(index, {})
    took = time.process_time() - started
    print(f"topics n=10000: {took * 1000:.0f} ms, {len(found)} topics")
    assert took < 5.0
    assert len(found) > 100


# --- the route ------------------------------------------------------------


def _note(client, content, tags=()):
    response = client.post("/entries", json={"content": content, "tags": list(tags)})
    assert response.status_code in (200, 201), response.text
    return response.json()


def test_structure_carries_named_topics_when_asked(client):
    glaze = [_note(client, f"Glaze test {i}", ["glazing"]) for i in range(4)]
    garden = [_note(client, f"Garden bed {i}", ["garden"]) for i in range(4)]
    for group in (glaze, garden):
        for i, a in enumerate(group):
            for b in group[i + 1 :]:
                client.post(f"/entries/{a['id']}/links", json={"target_id": b["id"]})
    client.post(f"/entries/{glaze[0]['id']}/links", json={"target_id": garden[0]["id"]})
    plain = client.get("/graph/structure").json()
    assert "topics" not in plain
    body = client.get("/graph/structure?topics=1").json()
    names = sorted(t["name"] for t in body["topics"])
    assert names == ["#garden", "#glazing"], names
    assert body["topic_of"][str(glaze[1]["id"])] != body["topic_of"][str(garden[1]["id"])]


def test_a_private_note_lends_no_words_to_a_name(client, session):
    from tessellate.core.database import Entry

    made = [_note(client, f"Zebra secret plan {i}") for i in range(3)]
    for i, a in enumerate(made):
        for b in made[i + 1 :]:
            client.post(f"/entries/{a['id']}/links", json={"target_id": b["id"]})
    for note in made:
        row = session.get(Entry, note["id"])
        row.is_private = True
    session.commit()
    body = client.get("/graph/structure?topics=1").json()
    assert all("zebra" not in t["name"].lower() for t in body["topics"])


def test_a_topic_no_strong_term_names_takes_a_weak_one_then_its_core_title():
    """The owner, 2026-10-11: a cluster chip read "Topic 2". A term two notes
    share names it below the share bar; with none, its most linked note's
    title does; "Topic N" is left for notes with no readable title."""
    index = _index(8, _clique([1, 2, 3, 4, 5, 6, 7, 8]) + [(1, 3), (1, 5)])
    weak = {i: {("word", f"own{i}")} for i in range(1, 9)}
    weak[2] |= {("tag", "kiln")}
    weak[3] |= {("tag", "kiln")}
    assert topics.build(index, weak)[0]["name"] == "#kiln"
    plain = {i: {("word", f"own{i}")} for i in range(1, 9)}
    found = topics.build(index, plain, {i: f"Note {i}" for i in range(1, 9)})
    assert found[0]["name"] == "Around Note 1"
    long = topics.build(index, plain, {1: "A" * 60})
    assert long[0]["name"] == "Around " + "A" * 39 + "…"
    assert topics.build(index, plain, {})[0]["name"] == "Topic 1"
