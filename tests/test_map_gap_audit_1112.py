"""The gap audit's topic tools (MINDMAP_PLAN rows 5 to 8, 9, 12): the pure parts
run in node, and the doors are checked where a person finds them."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
MORE = (JS / "whiteboard-map-more.js").read_text(encoding="utf-8")
MAP = (JS / "whiteboard-map.js").read_text(encoding="utf-8")
BOARD = (JS / "whiteboard.js").read_text(encoding="utf-8")


def _function(name: str) -> str:
    start = MORE.index(f"function {name}(")
    return MORE[start : MORE.index("\n  }\n", start) + 5]


def _run(body: str, names=(), extra="") -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    script = extra + "".join(_function(n) for n in names) + body
    return json.loads(subprocess.run([node, "-e", script], capture_output=True, text=True, check=True).stdout)


def test_timer_counts_down_on_a_fixed_clock():
    out = _run(
        "const t0=1000000;console.log(JSON.stringify({a:wbBrainstormLeft(t0,5,t0),b:wbBrainstormLeft(t0,5,t0+61000),"
        "c:wbBrainstormLeft(t0,5,t0+999999),d:wbBrainstormClock(247),e:wbBrainstormClock(300),f:wbBrainstormClock(0)}))",
        ("wbBrainstormLeft", "wbBrainstormClock"),
    )
    assert out == {"a": 300, "b": 239, "c": 0, "d": "4:07", "e": "5:00", "f": "0:00"}


def test_shape_patch_copies_look_and_layout_and_clears_what_is_missing():
    out = _run(
        "console.log(JSON.stringify(wbShapePatch({color:'red',branch_layout:'radial',note:'keep'},['color','shape'])))",
        ("wbShapePatch",),
    )
    assert out == {"color": "red", "shape": None, "branch_layout": "radial"}


def test_templates_are_outlines_and_unknown_is_empty():
    src = MORE[MORE.index("const WB_TOPIC_TEMPLATES"): MORE.index("});", MORE.index("const WB_TOPIC_TEMPLATES")) + 3]
    out = _run(
        "console.log(JSON.stringify({p:wbTemplateOutline('pros'),s:wbTemplateOutline('swot').split('\\n').length,x:wbTemplateOutline('nope')}))",
        ("wbTemplateOutline",),
        src + "\n",
    )
    assert out == {"p": "Pros\nCons", "s": 4, "x": ""}


def test_every_door_is_in_the_palette_and_the_topic_menu():
    for name in ("imageFromLink", "copyShape", "pasteShape", "pickTemplate", "saveBranch", "secondRoot"):
        assert f"wbMapLazy.{name}(node)" in MAP
        assert f"wbMapLazy.{name}(mapNode)" in BOARD
        assert f"{name}:" in MORE
    assert "wbMapLazy.startTimer(5)" in MAP


def test_second_root_link_carries_its_label_and_is_one_undo_step():
    body = MORE[MORE.index("async function wbSecondRoot"):]
    body = body[: body.index("\n  }\n")]
    assert "wbRecordGesture(" in body and "label }" in body and '"link-straight"' in body


def test_chat_map_opens_as_a_proposal_to_keep_or_discard():
    quick = (JS / "quick-note.js").read_text(encoding="utf-8")
    keep = quick[quick.index("async function chatKeep"): quick.index("async function saveChatAnswerAsNote")]
    assert "await openWhiteboardBoard(board.id);" in keep and "chatProposalBar(board)" in keep
    assert '"Keep the map"' in keep and '"Discard it"' in keep and "method: \"DELETE\"" in keep
