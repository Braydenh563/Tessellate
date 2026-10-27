"""A text box or sticky grows as its words are typed (wbdog-1026: 177px of words sat behind a scroll bar in a 62px box)."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WB = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")
FORMAT = (ROOT / "frontend" / "js" / "whiteboard-format.js").read_text(encoding="utf-8")


def _grow(height: int, scroll: int, words_h: int, el_h: int, sticker: bool = False):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    a = WB.index("function wbTextFitHeight(")
    b = WB.index("function wbEndTextEdit(")
    fns = WB[a:b]
    script = (
        "const WB_KIND_INFO = { object: { payload: (d) => ({ height: d.height }) } }; let bars = 0;"
        "const wbUpdateSelectionBar = () => bars++;"
        + fns
        + f"const words = {{ scrollHeight: {scroll}, offsetHeight: {words_h} }};"
        f"const el = {{ offsetHeight: {el_h}, style: {{}}, querySelector: () => words }};"
        "const contentEl = { closest: () => el };"
        f"const d = {{ height: {height}, data: {{ sticker: {json.dumps(sticker)} }} }};"
        "const grew = wbGrowBoxToWords(contentEl, d);"
        "console.log(JSON.stringify({ grew, h: d.height, css: el.style.height || null, before: contentEl.wbBeforeGrow || null }));"
    )
    return json.loads(subprocess.run([node, "-e", script], capture_output=True, text=True, check=True).stdout)


def test_words_taller_than_the_box_grow_it_by_the_chrome_too():
    out = _grow(height=80, scroll=177, words_h=62, el_h=80)
    assert out == {"grew": True, "h": 195, "css": "195px", "before": {"height": 80}}


def test_a_box_that_fits_never_shrinks_or_moves():
    out = _grow(height=140, scroll=40, words_h=124, el_h=140)
    assert out["grew"] is False and out["h"] == 140 and out["css"] is None


def test_an_emoji_sticker_is_left_alone():
    assert _grow(height=80, scroll=400, words_h=62, el_h=80, sticker=True)["grew"] is False


def test_typing_and_the_command_share_one_measure():
    assert 'content.on("input"' in WB and "wbGrowBoxToWords(this, d)" in WB
    assert "wbTextFitHeight(el)" in FORMAT and "words.scrollHeight" not in FORMAT.split("function wbAutoSizeSelection")[1][:2500]
