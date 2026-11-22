"""`/graph/local` (focus mode) at notebook scale (BACKLOG 29b item 4).

It used to load every note as an ORM object, index every link, thread and tag
and walk every link again for edge direction, on every call, to draw a
neighbourhood of a dozen notes. The topology (who is joined to whom) is now
built from columns only and kept once per version of the notebook, the way
centrality and the similarity sweep already were; a call reads only the notes
it draws.

The assertions pin the shape, not a wall clock (a clock failed on a busy CI
runner in tests/test_relations_kg2.py): five times the notes may cost a warm
call at most three times the time, and a warm call builds the topology zero
times. The numbers print with -s.
"""
from __future__ import annotations

import json
import random
import time

import pytest
from sqlalchemy import delete, insert, select

from tessellate.api import routes_graph
from tessellate.core.database import Entry, EntryLink
from tessellate.entry import paths


def _notebook(session, n: int, seed: int = 11) -> list[int]:
    rng = random.Random(seed)
    tags = [f"t{i}" for i in range(max(2, n // 8))]
    session.execute(
        insert(Entry),
        [
            {"content": f"Note {i}", "tags": json.dumps(rng.sample(tags, 2)), "is_private": False}
            for i in range(n)
        ],
    )
    session.commit()
    ids = list(session.scalars(select(Entry.id)))
    pairs = {(rng.choice(ids), rng.choice(ids)) for _ in range(n * 2)}
    session.execute(
        insert(EntryLink),
        [{"source_entry_id": a, "target_entry_id": b} for a, b in pairs if a != b],
    )
    session.commit()
    return ids


@pytest.fixture()
def build_calls(monkeypatch):
    calls: list[str] = []
    real = paths.build_light

    def counting(*args, **kwargs):
        # The focus topology only (every live note). The map's PageRank
        # builds its own picture once per version (`routes_graph._centrality`,
        # drafts left out), shared with `/graph`, and is not what these
        # tests count.
        if kwargs.get("drafts", True):
            calls.append("build")
        return real(*args, **kwargs)

    monkeypatch.setattr(paths, "build_light", counting)
    return calls


def _local(client, centre: int) -> dict:
    resp = client.get(f"/graph/local/{centre}", params={"depth": 2})
    assert resp.status_code == 200
    return resp.json()


def test_warm_focus_calls_do_not_rebuild_the_topology(client, session, build_calls):
    ids = _notebook(session, 300)
    routes_graph.reset_graph_cache()
    first = _local(client, ids[0])
    assert len(build_calls) == 1
    again = _local(client, ids[0])
    other = _local(client, ids[5])
    assert again == first
    assert other["nodes"]
    assert len(build_calls) == 1, "a second focus call rebuilt the whole notebook's index"


def test_a_write_makes_the_next_focus_call_see_it(client, session, build_calls):
    ids = _notebook(session, 120)
    routes_graph.reset_graph_cache()
    _local(client, ids[0])
    session.add(EntryLink(source_entry_id=ids[0], target_entry_id=ids[-1]))
    session.commit()
    after = _local(client, ids[0])
    assert len(build_calls) == 2
    pairs = {frozenset((e["source"], e["target"])) for e in after["edges"]}
    assert frozenset((ids[0], ids[-1])) in pairs


def test_the_column_only_index_agrees_with_the_full_one(session):
    """`build_light` is `build` over columns: same notes, same steps."""
    ids = _notebook(session, 400, seed=3)
    session.add(Entry(content="gone", is_deleted=True, tags=json.dumps(["t1"])))
    session.commit()
    full = paths.build(session)
    light = paths.build_light(session)
    assert set(light.entries) == set(full.entries)
    for node in ids:
        assert light.neighbours(node) == full.neighbours(node), node
    assert light.hub_tags == full.hub_tags


def test_a_warm_call_is_flat_in_the_notebook_size(client, session):
    took: dict[int, float] = {}
    for n in (2000, 10000):
        session.execute(delete(EntryLink))
        session.execute(delete(Entry))
        session.commit()
        ids = _notebook(session, n)
        routes_graph.reset_graph_cache()
        started = time.process_time()
        _local(client, ids[0])
        cold = time.process_time() - started
        runs = []
        for centre in ids[1:6]:
            started = time.process_time()
            _local(client, centre)
            runs.append(time.process_time() - started)
        took[n] = min(runs)
        print(f"graph/local n={n}: cold {cold * 1000:.0f} ms, warm {took[n] * 1000:.0f} ms")
    assert took[10000] < 3 * took[2000] + 0.05, took
    assert took[10000] < 5.0, took
