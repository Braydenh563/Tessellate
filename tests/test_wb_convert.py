"""GraphML, Miro and EMF in, and PlantUML in (L-whiteboard-41, 45): the readers are pure, so each is checked on a
fixture, and the hostile files (a billion-laughs document, an oversized one) are refused before they are read."""

from __future__ import annotations

import base64
import json
import struct

import pytest
from fastapi import HTTPException

from tessellate.api import wb_convert

GRAPHML = """<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns" xmlns:y="http://www.yworks.com/xml/graphml">
  <key id="d0" for="node" attr.name="label" attr.type="string"/>
  <key id="d1" for="edge" attr.name="label" attr.type="string"/>
  <graph id="G" edgedefault="directed">
    <node id="a"><data key="d0">Start here</data></node>
    <node id="b"><data key="d0">Decide</data></node>
    <node id="c"/>
    <edge id="e1" source="a" target="b"><data key="d1">go</data></edge>
    <edge id="e2" source="b" target="c"/>
    <edge id="e3" source="b" target="ghost"/>
  </graph>
</graphml>"""


def test_graphml_nodes_edges_and_labels():
    out = wb_convert.parse_graphml(GRAPHML)
    graph = out["graph"]
    assert [n["text"] for n in graph["nodes"]] == ["Start here", "Decide", "c"]
    assert [(e["from"], e["to"], e["label"], e["arrow"]) for e in graph["edges"]] == [("a", "b", "go", True), ("b", "c", "", True)]
    assert graph["skipped"] == 1, "the edge to a node that is not there is counted, not drawn"


def test_graphml_yed_labels_geometry_and_nested_graphs():
    text = """<graphml xmlns="http://graphml.graphdrawing.org/xmlns" xmlns:y="http://www.yworks.com/xml/graphml">
      <key id="g" for="node" yfiles.type="nodegraphics"/>
      <graph edgedefault="undirected">
        <node id="n1"><data key="g"><y:ShapeNode><y:Geometry x="10" y="20" width="90" height="40"/><y:NodeLabel>One</y:NodeLabel><y:Shape type="diamond"/></y:ShapeNode></data></node>
        <node id="grp"><graph id="grp:" edgedefault="directed"><node id="n2"/></graph><data key="g"><y:ShapeNode><y:NodeLabel>Group</y:NodeLabel></y:ShapeNode></data></node>
        <edge source="n1" target="n2"/>
      </graph></graphml>"""
    graph = wb_convert.parse_graphml(text)["graph"]
    one = graph["nodes"][0]
    assert one["text"] == "One" and one["shape"] == "diamond" and (one["x"], one["y"], one["w"], one["h"]) == (10, 20, 90, 40)
    assert graph["subgraphs"][0]["title"] == "Group" and graph["nodes"][1]["group"] == "grp"
    assert graph["edges"][0]["arrow"] is False, "an undirected graph draws lines"


def test_graphml_billion_laughs_is_refused():
    laughs = (
        '<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY lol "lol"><!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">'
        '<!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">]>'
        '<graphml xmlns="http://graphml.graphdrawing.org/xmlns"><graph><node id="&lol3;"/></graph></graphml>'
    )
    with pytest.raises(HTTPException) as caught:
        wb_convert.parse_graphml(laughs)
    assert caught.value.status_code == 422 and "document type" in caught.value.detail


def test_an_oversized_file_is_refused_before_it_is_parsed():
    big = "x" * (wb_convert.MAX_CONVERT_CHARS + 1)
    for reader in (wb_convert.parse_graphml, wb_convert.parse_miro, wb_convert.parse_plantuml):
        with pytest.raises(HTTPException) as caught:
            reader(big)
        assert caught.value.status_code == 413
    with pytest.raises(HTTPException) as caught:
        wb_convert.inspect_emf(b"\0" * (wb_convert.MAX_EMF_BYTES + 1))
    assert caught.value.status_code == 413


def test_a_diagram_with_too_many_shapes_is_refused_not_trimmed():
    nodes = "".join(f'<node id="n{i}"/>' for i in range(wb_convert.MAX_NODES + 1))
    with pytest.raises(HTTPException) as caught:
        wb_convert.parse_graphml(f'<graphml xmlns="http://graphml.graphdrawing.org/xmlns"><graph>{nodes}</graph></graphml>')
    assert caught.value.status_code == 413


#: Miro REST API v2 "get items on board" shape: documented, versioned, with positions.
MIRO = {
    "data": [
        {"id": "3458764", "type": "frame", "data": {"title": "Sprint"}, "position": {"x": 500, "y": 300}, "geometry": {"width": 1000, "height": 600}},
        {"id": "1", "type": "sticky_note", "data": {"content": "<p>Ship it</p><p>by Friday</p>", "shape": "square"}, "style": {"fillColor": "#fff9b1"}, "position": {"x": 300, "y": 200}, "geometry": {"width": 199}},
        {"id": "2", "type": "shape", "data": {"content": "<p>Review &amp; merge</p>", "shape": "rhombus"}, "position": {"x": 700, "y": 200}, "geometry": {"width": 200, "height": 120}},
        {"id": "3", "type": "shape", "data": {"content": "Outside"}, "position": {"x": 5000, "y": 5000}, "geometry": {"width": 100, "height": 100}},
        {"id": "9", "type": "connector", "startItem": {"id": "1"}, "endItem": {"id": "2"}, "captions": [{"content": "<p>then</p>"}], "style": {"endStrokeCap": "stealth", "strokeStyle": "dashed"}},
        {"id": "10", "type": "connector", "startItem": {"id": "1"}, "endItem": {"id": "nope"}},
        {"id": "11", "type": "image", "data": {}, "position": {"x": 0, "y": 0}},
    ]
}


def test_miro_rest_json_shapes_frames_and_connectors():
    graph = wb_convert.parse_miro(json.dumps(MIRO))["graph"]
    by = {n["id"]: n for n in graph["nodes"]}
    assert by["1"]["text"] == "Ship it\nby Friday" and by["1"]["fill"] == "#fff9b1" and by["1"]["group"] == "3458764"
    assert by["2"]["text"] == "Review & merge" and by["2"]["shape"] == "diamond" and (by["2"]["x"], by["2"]["y"]) == (700, 200)
    assert by["3"]["group"] is None, "a shape outside every frame belongs to none"
    assert graph["frames"][0]["title"] == "Sprint" and graph["frames"][0]["x"] == 0 and graph["frames"][0]["w"] == 1000
    assert graph["edges"] == [{"from": "1", "to": "2", "label": "then", "arrow": True, "dashed": True}]
    assert graph["skipped"] == 2, "the image and the connector to a missing item"
    assert graph["positioned"] is True


def test_miro_accepts_a_bare_list_and_refuses_other_json():
    assert wb_convert.parse_miro(json.dumps(MIRO["data"]))["graph"]["nodes"]
    for bad in ("not json", '{"hello": 1}', '{"data": []}'):
        with pytest.raises(HTTPException) as caught:
            wb_convert.parse_miro(bad)
        assert caught.value.status_code == 422


def _emf(width: int, height: int, size: int = 120) -> bytes:
    header = struct.pack("<II", 1, 88) + struct.pack("<iiii", 0, 0, width - 1, height - 1) + struct.pack("<iiii", 0, 0, 100, 100)
    header += struct.pack("<I", 0x464D4520) + b"\0" * (88 - len(header) - 4)
    return header + b"\0" * (size - 88)


def test_emf_is_measured_and_not_pretended_to_be_drawn():
    out = wb_convert.inspect_emf(_emf(640, 480))
    assert (out["kind"], out["width"], out["height"]) == ("emf", 640, 480)
    assert "Inkscape" in out["message"] and "cannot draw" in out["message"]


def test_a_file_that_is_not_an_emf_is_refused():
    for bad in (b"MZ" + b"\0" * 200, b"short", _emf(10, 10)[:60]):
        with pytest.raises(HTTPException) as caught:
            wb_convert.inspect_emf(bad)
        assert caught.value.status_code == 422


CLASSES = """@startuml
' a comment
class Animal {
  +name : String
  +speak()
}
interface Pet
abstract class Base
Animal <|-- Dog
Animal "1" *-- "many" Leg : has
Dog ..|> Pet
Dog --> Owner : belongs to
Dog : +bark()
skinparam monochrome true
@enduml"""


def test_plantuml_class_diagram():
    out = wb_convert.parse_plantuml(CLASSES)
    assert out["diagram"] == "class"
    graph = out["graph"]
    by = {n["id"]: n for n in graph["nodes"]}
    assert by["Animal"]["text"] == "Animal\n+name : String\n+speak()" and by["Animal"]["h"] == 90
    assert by["Dog"]["text"] == "Dog\n+bark()"
    assert set(by) == {"Animal", "Pet", "Base", "Dog", "Leg", "Owner"}
    edges = {(e["from"], e["to"]): e for e in graph["edges"]}
    assert edges[("Animal", "Dog")]["startCap"] == "triangle"
    assert edges[("Animal", "Leg")]["startCap"] == "diamond-filled" and edges[("Animal", "Leg")]["label"] == "has"
    assert edges[("Dog", "Pet")]["dashed"] is True and edges[("Dog", "Pet")]["endCap"] == "triangle"
    assert edges[("Dog", "Owner")]["arrow"] is True and edges[("Dog", "Owner")]["label"] == "belongs to"


SEQUENCE = """@startuml
actor User
participant "Web app" as Web
database DB
User -> Web : open
Web --> DB : query
DB --> Web : rows
Web <- User : ack
note over Web, DB : cached
loop every minute
  Web -> Web : poll
end
@enduml"""


def test_plantuml_sequence_diagram():
    out = wb_convert.parse_plantuml(SEQUENCE)
    assert out["diagram"] == "sequence"
    seq = out["sequence"]
    assert [(p["id"], p["text"], p["actor"]) for p in seq["participants"]] == [("User", "User", True), ("Web", "Web app", False), ("DB", "DB", False)]
    msgs = [s for s in seq["steps"] if s["kind"] == "message"]
    assert [(m["from"], m["to"], m["text"], m["dashed"]) for m in msgs] == [
        ("User", "Web", "open", False), ("Web", "DB", "query", True), ("DB", "Web", "rows", True), ("User", "Web", "ack", False), ("Web", "Web", "poll", False)]
    assert seq["steps"][4]["kind"] == "note" and seq["steps"][4]["over"] == ["Web", "DB"]
    assert any(s["kind"] == "block" and s["text"] == "loop every minute" for s in seq["steps"])


ACTIVITY = """@startuml
start
:Read the order;
if (In stock?) then (yes)
  :Pack it;
else (no)
  :Back-order;
endif
while (More items?) is (yes)
  :Scan;
endwhile (no)
stop
@enduml"""


def test_plantuml_activity_diagram():
    out = wb_convert.parse_plantuml(ACTIVITY)
    assert out["diagram"] == "activity"
    graph = out["graph"]
    text = {n["id"]: n["text"] for n in graph["nodes"]}
    ids = {v: k for k, v in text.items()}
    assert [n["shape"] for n in graph["nodes"] if n["text"] == "In stock?"] == ["diamond"]
    edges = {(text[e["from"]], text[e["to"]]): e["label"] for e in graph["edges"]}
    assert edges[("In stock?", "Pack it")] == "yes" and edges[("In stock?", "Back-order")] == "no"
    assert ("Pack it", "More items?") in edges and ("Back-order", "More items?") in edges, "both branches rejoin"
    assert edges[("More items?", "Scan")] == "yes" and edges[("Scan", "More items?")] == ""
    assert edges[("More items?", "End")] == "no" and ids["Start"]


def test_plantuml_unknown_kind_is_said_not_guessed():
    with pytest.raises(HTTPException) as caught:
        wb_convert.parse_plantuml("@startmindmap\n* root\n** child\n@endmindmap")
    assert caught.value.status_code == 422


def test_the_route_reads_each_format(ai_client):
    out = ai_client.post("/whiteboard/convert", json={"format": "graphml", "content": GRAPHML})
    assert out.status_code == 200 and out.json()["kind"] == "graph"
    auto = ai_client.post("/whiteboard/convert", json={"content": CLASSES})
    assert auto.status_code == 200 and auto.json()["diagram"] == "class"
    miro = ai_client.post("/whiteboard/convert", json={"content": json.dumps(MIRO)})
    assert miro.json()["graph"]["positioned"] is True
    emf = ai_client.post("/whiteboard/convert", json={"format": "emf", "data_b64": base64.b64encode(_emf(32, 16)).decode()})
    assert emf.json()["width"] == 32
    unknown = ai_client.post("/whiteboard/convert", json={"format": "visio", "content": "x"})
    words = ai_client.post("/whiteboard/convert", json={"content": "just words"})
    assert unknown.status_code == 422 and words.status_code == 422


def test_the_route_refuses_an_oversized_body(ai_client):
    out = ai_client.post("/whiteboard/convert", json={"format": "graphml", "content": "x" * (wb_convert.MAX_CONVERT_CHARS + 5)})
    assert out.status_code in (413, 422)


def test_plantuml_named_boxes_and_packages_round_trip_with_the_boards_writer():
    text = (
        "@startuml\npackage \"Backend\" {\n  rectangle \"API\" as n1\n  diamond \"Ready?\" as n2\n}\n"
        "circle \"Done\" as n3\nn1 --> n2 : call\nn2 .. n3\nn3 ..> n1\n@enduml"
    )
    out = wb_convert.parse_plantuml(text)
    assert out["diagram"] == "elements"
    graph = out["graph"]
    by = {n["id"]: n for n in graph["nodes"]}
    assert by["n2"]["shape"] == "diamond" and by["n3"]["shape"] == "circle"
    assert by["n1"]["group"] == "g1" and by["n3"]["group"] is None and graph["subgraphs"][0]["title"] == "Backend"
    assert [(e["from"], e["to"], e["label"], e["arrow"], e["dashed"]) for e in graph["edges"]] == [
        ("n1", "n2", "call", True, False), ("n2", "n3", "", False, True), ("n3", "n1", "", True, True)]
