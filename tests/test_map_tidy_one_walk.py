"""Source text: the cost was query and layout-read counts per topic, measured in a profile, which pytest cannot count. L-mindmap-13 (2026-11-13): the tidy measures every topic in one walk.

Selecting a topic ends in a pointerup, which empties the size cache
(`wbClearMapNodeSizeCache`), so the Tab that follows laid the map out with one
`querySelector` and one layout read per topic: 3 to 6 ms of the 41-topic Tab
at 6x (`wbMapNodeSize` under `wbMapLayoutPositions`, profiled). A cache missing
topics is now filled by `wbIndexMapNodeElements`, one query and one batch of reads.
"""

from pathlib import Path

MAP = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "whiteboard-map.js").read_text(encoding="utf-8")


def _fn(name: str) -> str:
    rest = MAP[MAP.index(f"function {name}(") :]
    return rest[: rest.index("\n}\n") + 3]


def test_a_cold_size_cache_is_filled_in_one_walk_before_the_layout_reads_it():
    body = _fn("wbMapLayoutPositions")
    fill = body.index("wbMapNodeSize.fill?.(index.nodes);")
    assert "!wbMapNodeSizeCache?.has(o.id))) wbIndexMapNodeElements();" in MAP[MAP.index("wbMapNodeSize.fill = ") :][:200]
    assert fill < body.index("const sizes = new Map(index.nodes.map((o) => [o.id, wbMapNodeSize(o)]));")

