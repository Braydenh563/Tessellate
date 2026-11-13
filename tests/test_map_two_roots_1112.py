"""A second root on one map, joined by a labelled link (MINDMAP gap 12).

Two central topics already live on one map (a top-level topic is a trunk); the
link between them is a cross-link with a label. Decision 12's rules: FreeMind
and OPML carry it (private attribute in OPML), Markdown carries nothing. The
label used to be written by FreeMind only and read back by neither, so a
labelled link between two roots came home unlabelled.
"""

from tests.test_mindmap import _cross_link, _map, _node


def _two_roots(client):
    board = _map(client, name="Two centres")
    one = _node(client, board["id"], text="Product")
    _node(client, board["id"], parent_id=one["id"], text="Roadmap")
    two = _node(client, board["id"], text="Market")
    _node(client, board["id"], parent_id=two["id"], text="Rivals")
    _cross_link(client, board["id"], one["id"], two["id"], label="is shaped by")
    return board


def _round_trip(client, board, fmt):
    text = client.get(f"/whiteboard/boards/{board['id']}/export?format={fmt}").text
    back = client.post("/whiteboard/boards/import", json={"format": fmt, "content": text, "name": "Back"})
    assert back.status_code == 201, back.text
    return text, client.get(f"/whiteboard/boards/{back.json()['id']}/tree").json()


def _check(tree):
    assert sorted(r["text"] for r in tree["roots"]) == ["Market", "Product"]
    names = {r["id"]: r["text"] for r in tree["roots"]}
    [link] = tree["cross_links"]
    assert (names[link["from_id"]], names[link["to_id"]]) == ("Product", "Market")
    assert link["label"] == "is shaped by"


def test_the_label_between_two_roots_survives_freemind(client):
    text, tree = _round_trip(client, _two_roots(client), "freemind")
    assert 'MIDDLE_LABEL="is shaped by"' in text
    _check(tree)


def test_the_label_between_two_roots_survives_opml(client):
    text, tree = _round_trip(client, _two_roots(client), "opml")
    assert "_link_labels" in text
    _check(tree)


def test_an_unlabelled_link_writes_no_label_attribute(client):
    board = _map(client, name="Plain")
    a = _node(client, board["id"], text="A")
    b = _node(client, board["id"], text="B")
    _cross_link(client, board["id"], a["id"], b["id"])
    opml = client.get(f"/whiteboard/boards/{board['id']}/export?format=opml").text
    assert "_link_labels" not in opml


def test_a_hostile_label_list_is_ignored_not_trusted(client):
    content = (
        '<opml version="2.0"><head><title>x</title></head><body>'
        '<outline text="A" _id="a" _links="b" _link_labels="not json"/>'
        '<outline text="B" _id="b"/></body></opml>'
    )
    back = client.post("/whiteboard/boards/import", json={"format": "opml", "content": content, "name": "H"})
    assert back.status_code == 201, back.text
    tree = client.get(f"/whiteboard/boards/{back.json()['id']}/tree").json()
    assert len(tree["cross_links"]) == 1 and tree["cross_links"][0]["label"] == ""
