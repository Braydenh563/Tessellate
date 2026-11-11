"""Set as default style on a connector (driven on a map, 2026-11-11): a link sketch has no `d` path, so the
shape reader `wbSketchParsedData` returned null and the command answered "Select a shape..." for every link."""

from pathlib import Path

FMT = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "whiteboard-format.js").read_text(encoding="utf-8")


def test_the_default_style_reads_a_connector_without_needing_a_drawn_path() -> None:
    body = FMT[FMT.index("  function groupOf() {") : FMT.index("  async function setDefault()")]
    assert "wbSketchParsedData" not in body
    assert "JSON.parse(sketch.data)" in body
    assert '.startsWith("link-")' in body
