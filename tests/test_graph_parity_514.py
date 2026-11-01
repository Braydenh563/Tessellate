"""GRAPH_PLAN 514, the owner: "is the graph missing any core functionality and
abilities that the graphs in obsidian have??". The server half: the local
graph's depth and direction switches, and tags, unresolved [[names]] and
attachments as nodes, each opt-in like entities and documents."""

from __future__ import annotations

import io
from pathlib import Path


def _save(client, content, **extra):
    response = client.post("/entries", json={"content": content, **extra})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _link(client, a, b):
    assert client.post(f"/entries/{a}/links", json={"target_id": b}).status_code in (200, 201)


def _local(client, centre, **params):
    query = "&".join(f"{k}={str(v).lower()}" for k, v in params.items())
    return client.get(f"/graph/local/{centre}?{query}").json()


def _ids(body):
    return {n["id"] for n in body["nodes"]}


def test_local_incoming_and_outgoing_switches_follow_the_links_direction(client):
    a, b, c = _save(client, "centre note"), _save(client, "it links to me"), _save(client, "I link to it")
    _link(client, a, b)
    _link(client, c, a)
    assert _ids(_local(client, a, depth=1)) == {a, b, c}
    assert _ids(_local(client, a, depth=1, incoming=False)) == {a, b}
    assert _ids(_local(client, a, depth=1, outgoing=False)) == {a, c}
    # The edge says which way the link runs, whichever end the walk began at.
    edges = {(e["source"], e["target"]) for e in _local(client, a, depth=1)["edges"]}
    assert edges == {(a, b), (c, a)}


def test_neighbour_links_are_the_lines_between_notes_at_one_distance(client):
    a, b, c = _save(client, "hub note"), _save(client, "spoke one"), _save(client, "spoke two")
    _link(client, a, b)
    _link(client, a, c)
    _link(client, b, c)
    on = {frozenset((e["source"], e["target"])) for e in _local(client, a, depth=1)["edges"]}
    assert frozenset((b, c)) in on
    off = {frozenset((e["source"], e["target"])) for e in _local(client, a, depth=1, neighbours=False)["edges"]}
    assert off == {frozenset((a, b)), frozenset((a, c))}


def test_local_depth_walks_up_to_five_links(client):
    chain = [_save(client, f"chain note {i}") for i in range(7)]
    for left, right in zip(chain, chain[1:]):
        _link(client, left, right)
    assert _ids(_local(client, chain[0], depth=5)) == set(chain[:6])
    assert _ids(_local(client, chain[0], depth=1)) == set(chain[:2])


def test_tags_are_nodes_only_when_asked(client):
    a = _save(client, "soup", tags=["recipes"])
    b = _save(client, "bread", tags=["recipes", "baking"])
    assert not [n for n in client.get("/graph").json()["nodes"] if n.get("type") == "tag"]
    body = client.get("/graph?include_tags=true").json()
    tags = {n["id"]: n for n in body["nodes"] if n.get("type") == "tag"}
    assert set(tags) == {"tag:recipes", "tag:baking"}
    assert tags["tag:recipes"]["preview"] == "#recipes"
    edges = {(e["source"], e["target"]) for e in body["edges"] if e["kind"] == "tagged"}
    assert edges == {("tag:recipes", a), ("tag:recipes", b), ("tag:baking", b)}


def test_an_unresolved_wiki_name_is_a_ghost_node(client):
    _save(client, "# Present\n\nhere")
    holder = _save(client, "# Holder\n\nsee [[Present]] and [[Not written yet]]")
    assert not [n for n in client.get("/graph").json()["nodes"] if n.get("type") == "unresolved"]
    body = client.get("/graph?include_unresolved=true").json()
    ghosts = [n for n in body["nodes"] if n.get("type") == "unresolved"]
    assert [(g["id"], g["preview"]) for g in ghosts] == [("unresolved:not written yet", "Not written yet")]
    assert {"source": holder, "target": "unresolved:not written yet", "kind": "unresolved"} in body["edges"]


def test_attachments_are_nodes_only_when_asked(client):
    note = _save(client, "a note with a file")
    response = client.post(
        f"/entries/{note}/files", files={"file": ("lecture.pdf", io.BytesIO(b"%PDF-1.4 fake"), "application/pdf")}
    )
    assert response.status_code in (200, 201), response.text
    assert not [n for n in client.get("/graph").json()["nodes"] if n.get("type") == "attachment"]
    body = client.get("/graph?include_attachments=true").json()
    files = [n for n in body["nodes"] if n.get("type") == "attachment"]
    assert len(files) == 1 and files[0]["preview"] == "lecture.pdf"
    assert {"source": files[0]["id"], "target": note, "kind": "attachment"} in body["edges"]


def test_the_frontend_asks_for_what_the_switches_say():
    root = Path(__file__).resolve().parents[1] / "frontend"
    js = "\n".join(p.read_text(encoding="utf-8") for p in (root / "js").glob("graph*.js"))
    html = (root / "index.html").read_text(encoding="utf-8")
    for box, flag in (("graph-tags", "include_tags"), ("graph-unresolved", "include_unresolved"), ("graph-attachments", "include_attachments")):
        assert f'["{box}", "{flag}"]' in js, flag
        assert f'id="{box}"' in html, box
    assert "function graphLocalQuery(" in js
    assert 'graphLocalQuery("pane", 1)' in js and 'graphLocalQuery("focus", 2)' in js
    for prefix in ("focus", "pane"):
        for part in ("depth", "in", "out", "neighbours"):
            assert f'id="graph-{prefix}-{part}"' in html, (prefix, part)
    # A ghost's click writes the note with the name as its heading.
    assert "content: `# ${node.preview}`" in js


def test_arrows_text_fade_thickness_and_link_force_reach_the_drawing():
    root = Path(__file__).resolve().parents[1] / "frontend" / "js"
    canvas = (root / "graph-canvas.js").read_text(encoding="utf-8")
    assert 'else if (arrows && edge.kind === "link" && !edge.two_way) {' in canvas and "gcLinkSpark(bucket, a, bow, b, k, sparkRich);" in canvas
    # The width reaches the stroke through gcSetStroke (gr1-1101: a hairline only while the map moves).
    assert "gcSetStroke(ctx, s, style.width * widthScale * (bucket.wide ? 0.8 : 1), k, alpha, !!style.dash);" in canvas
    assert "k > labelZoom" in canvas and "linkForce: Number(" in canvas
    worker = (root / "graph-worker.js").read_text(encoding="utf-8")
    # Times a cross-category factor since INBOX 693 (`crossStrength`).
    assert "* linkScale * across;" in worker and ".strength(linkStrength);" in worker


def test_arrows_are_off_by_default_and_drawn_as_sparks():
    """The owner: "I want graph arrows off by default on the graph, can you
    also make the graph arrows impressive and styled in a way unique to the
    app??". Off unless stored "1"; a comet-tailed spark 70% along the link on
    a two-step glow, the line wider on its source half, batched per bucket; a
    drifting spark on the pointed-at note's links only when motion is allowed."""
    root = Path(__file__).resolve().parents[1] / "frontend"
    html = (root / "index.html").read_text(encoding="utf-8")
    assert '<input type="checkbox" id="graph-arrows">' in html
    canvas = (root / "js" / "graph-canvas.js").read_text(encoding="utf-8")
    assert 'prefs.get("graph-arrows", null) === "1"' in canvas
    graph = (root / "js" / "graph.js").read_text(encoding="utf-8")
    assert '"graph-arrows": false,' in graph and 'GRAPH_STORED_OFF = ["graph-arrows"]' in graph
    spark = canvas[canvas.index("function gcLinkSpark") : canvas.index("function gcFillSparks")]
    assert "gcQuadAt(a, c, b, 0.7)" in spark and "bucket.wide.quadraticCurveTo" in spark
    assert "bucket.glows.arc(" in spark and "bucket.sparks.quadraticCurveTo(" in spark
    drifting = canvas[canvas.index("const drifting =") :][:400]
    # One resolved value, through `gcStill` (Brief 100, INBOX 1506).
    still = canvas[canvas.index("function gcStill(") :][:400]
    assert "!gcStill()" in drifting
    assert "reducedMotionWanted()" in still and "matchMedia" not in still
