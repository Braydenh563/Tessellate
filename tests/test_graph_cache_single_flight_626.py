"""L-world-class-626: requests that arrive together while the notebook is
changing each rebuilt `/graph/structure` (community detection, the slowest
thing the graph does), so eight clients paid eight builds of the same
version. One build per name and version runs; the others wait for it."""

from __future__ import annotations

import threading
import time

from tessellate.api import routes_graph


def test_concurrent_asks_for_one_version_build_it_once():
    routes_graph.reset_graph_cache()
    calls = []
    start = threading.Barrier(8)

    def build():
        calls.append(1)
        time.sleep(0.05)
        return {"built": len(calls)}

    results = []

    def ask():
        start.wait()
        results.append(routes_graph._cached("structure", ("v1",), build))

    threads = [threading.Thread(target=ask) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(calls) == 1
    assert results == [{"built": 1}] * 8


def test_a_new_version_still_builds_and_other_names_do_not_wait():
    routes_graph.reset_graph_cache()
    assert routes_graph._cached("structure", ("v1",), lambda: 1) == 1
    assert routes_graph._cached("structure", ("v2",), lambda: 2) == 2
    assert routes_graph._cached("topics", ("v2",), lambda: 3) == 3
    assert routes_graph._cached("structure", ("v2",), lambda: 99) == 2


def test_a_build_that_raises_lets_the_next_ask_build():
    routes_graph.reset_graph_cache()

    def broken():
        raise RuntimeError("boom")

    try:
        routes_graph._cached("structure", ("v1",), broken)
    except RuntimeError:
        pass
    assert routes_graph._cached("structure", ("v1",), lambda: 5) == 5
