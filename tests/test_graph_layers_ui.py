"""The Graph UI asks for the document and entity layers in the map and the trace (L-graph-14)."""

from __future__ import annotations

from pathlib import Path

JS = Path(__file__).resolve().parent.parent / "frontend" / "js"


def graph_js_text():
    """The graph scripts load lazily, outside the app.js list: read them by name."""
    return "\n".join(
        (JS / name).read_text(encoding="utf-8") for name in ("graph.js", "graph-canvas.js")
    )


def test_the_map_request_carries_the_layer_flags():
    js = graph_js_text()
    assert '["graph-entities", "include_entities"]' in js
    assert '["graph-documents", "include_documents"]' in js


def test_the_trace_request_sends_the_layers_and_accepts_layer_ends():
    js = graph_js_text()
    assert "${graphPathLayerQuery()}" in js
    body = js.split("function graphPathLayerQuery()", 1)[1].split("\n  }\n", 1)[0]  # nested in runTrace (global-scope ratchet)
    for needle in ("graph-documents", "graph-entities", "&documents=true", "&entities=true"):
        assert needle in body
    assert 'startsWith("document:")' in body and 'startsWith("entity:")' in body


def test_a_click_on_a_layer_node_picks_a_trace_end_before_it_opens_the_page():
    js = graph_js_text()
    pick = js.index('traceModeActive && (node.type === "entity" || node.type === "document")')
    assert pick < js.index("openEntityPage(String(node.id)")
    assert pick < js.index("if (gcOpenNodeTarget(node)) return;")
