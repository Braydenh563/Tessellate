"""A shape grows, in proportion, until the words typed into it fit (wbdog-1026: 80 characters ran 100px past a 100x60 rectangle)."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WB = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")
FORMAT = (ROOT / "frontend" / "js" / "whiteboard-format.js").read_text(encoding="utf-8")


def _grow(need_h: int, area_h: int):
    """Run wbGrowShapeToLabel against a fake shape whose area scales with it."""
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    a = FORMAT.index("function wbAutoSizeFactors(")
    b = FORMAT.index("//: Grow to fit: a shape taller")
    fns = FORMAT[a:b]
    script = (
        "const saved = []; let scale = 1; let renders = 0;"
        "const sketch = { id: 1 };"
        f"const label = {{ getBBox: () => ({{ width: 100, height: {need_h} }}) }};"
        f"const group = {{ querySelector: () => label }};"
        "global.document = { querySelector: () => group };"
        f"const wbShapeLabelPlace = () => ({{ area: {{ w: 100, h: {area_h} * scale }} }});"
        "const wbSketchParsedData = () => ({ d: 'M 0 0' });"
        "const wbPathBBox = () => ({ minX: 0, minY: 0 });"
        "const wbTransformPathD = (d, o) => { scale *= o.sy; return d; };"
        "const wbSaveSketchD = async () => { saved.push(scale); };"
        "const renderWhiteboardNow = () => { renders++; };"
        + fns
        + "wbGrowShapeToLabel(sketch).then((changed) => console.log(JSON.stringify({ changed, saved, renders })));"
    )
    return json.loads(subprocess.run([node, "-e", script], capture_output=True, text=True, check=True).stdout)


def test_words_that_overflow_grow_the_shape_in_rounds_until_they_fit():
    out = _grow(need_h=160, area_h=40)
    assert out["changed"] is True and 1 <= len(out["saved"]) <= 4
    # Grown on both sides by the root of what was missing, not 4x the height at once.
    assert out["saved"][0] < 3


def test_words_that_fit_leave_the_shape_alone():
    out = _grow(need_h=30, area_h=40)
    assert out == {"changed": False, "saved": [], "renders": 0}


def test_typing_a_label_grows_the_shape_as_part_of_the_same_step():
    start = WB.index("const finish = async () => {")
    body = WB[start : WB.index("editor.addEventListener(\"keydown\"", start)]
    assert body.index("wbPushUndo") < body.index("wbGrowShapeToLabel(sketch)")
    assert "!parsed.label_fit" in body
