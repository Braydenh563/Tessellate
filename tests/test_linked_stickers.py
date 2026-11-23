"""Source text: the behaviour is front-end script that pytest cannot run without a browser, so these pin the code's text.

Linked stickers (MINDMAP_PLAN 14.4): one placed icon or emoji edited, every copy follows."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MORE = (ROOT / "frontend" / "js" / "whiteboard-map-more.js").read_text(encoding="utf-8")
CMD = (ROOT / "frontend" / "js" / "whiteboard-commands.js").read_text(encoding="utf-8")
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
PLAN = (ROOT / "docs" / "roadmap" / "WHITEBOARD_PLAN.md").read_text(encoding="utf-8")


def _function(name: str) -> str:
    start = MORE.index(f"function {name}(")
    return MORE[start : MORE.index("\n  }\n", start) + 5]


def _run(expr: str):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    code = "function wbSketchData(s) { try { return JSON.parse(s.data); } catch { return null; } }" + _function("wbStickerKey") + _function("wbStickerCopiesOf") + f"console.log(JSON.stringify({expr}));"
    return json.loads(subprocess.run([node, "-e", code], capture_output=True, text=True, check=True).stdout)


def test_a_sticker_is_known_by_its_icon_or_its_glyph() -> None:
    assert _run('wbStickerKey("sketch", {data: JSON.stringify({icon: "star"})})') == "icon:star"
    assert _run('wbStickerKey("object", {kind: "text", data: {sticker: true, content: "🔥"}})') == "emoji:🔥"
    assert _run('wbStickerKey("object", {kind: "text", data: {content: "plain"}})') is None
    assert _run('wbStickerKey("sketch", {data: JSON.stringify({d: "M0"})})') is None


def test_copies_are_every_item_with_the_same_key() -> None:
    expr = (
        'wbStickerCopiesOf("emoji:🔥", {sketches: [{id: 1, data: JSON.stringify({icon: "star"})}, {id: 2, data: JSON.stringify({icon: "star"})}],'
        ' objects: [{id: 3, kind: "text", data: {sticker: true, content: "🔥"}},'
        ' {id: 4, kind: "text", data: {sticker: true, content: "🔥"}}, {id: 5, kind: "text", data: {content: "🔥"}}]}).map((e) => e.item.id)'
    )
    assert _run(expr) == [3, 4]


def test_the_copies_follow_through_one_undo_step_and_the_ui_offers_it() -> None:
    match = MORE.split("async function wbStickerMatch(")[1].split("\n  }\n")[0]
    assert "wbRecordGesture" in match and "wbSaveMany" in match
    swap = MORE.split("async function wbStickerSwap(")[1].split("\n  }\n")[0]
    assert "wbRecordGesture" in swap and "wbSaveMany" in swap
    for command in ("sticker-match", "sticker-swap"):
        assert f'id: "{command}"' in CMD and f'data-wb-cmd="{command}"' in HTML
    assert "wbMapLazy.stickerMatch()" in CMD and "wbMapLazy.stickerSwap()" in CMD


def test_decision_25_points_at_the_plan_that_supersedes_it() -> None:
    block = PLAN.split("25. **The object library is independent copies**")[1].split("\n26.")[0]
    assert "MINDMAP_PLAN" in block and "14.4" in block


def test_swap_everywhere_replaces_an_icon_path_in_every_copy_keeping_place_and_paint() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    swap = MORE.split("async function wbStickerSwap(")[1].split("\n  }\n")[0]
    for needed in ("wbLoadIcons", "wbPathBBox", "wbTransformPathD", "data.icon = choice.value", "wbRecordGesture", "wbSaveMany"):
        assert needed in swap
    # Run the real function with stubs: two copies of "star" at different places, scales and paints.
    body = MORE[MORE.index("async function wbStickerSwap(") : MORE.index("\n  }\n", MORE.index("async function wbStickerSwap(")) + 5]
    code = (
        "const sk=(d,extra)=>({id:extra.id,data:JSON.stringify({d,icon:'star',fill:'#f00',opacity:0.5,library_ref:'icons/star',...extra.o})});"
        "const a=sk('M10 10 L30 10 L30 30 L10 30 Z',{id:1}), b=sk('M100 100 L200 100 L200 200 L100 200 Z',{id:2,o:{fill:'#0a0'}});"
        "let saved=0,gestures=0;"
        "const wbStickerCopies=()=>[{kind:'sketch',item:a},{kind:'sketch',item:b}];"
        "const pickIconOrEmoji=async()=>({kind:'icon',value:'heart'});"
        "const wbLoadIcons=async()=>({heart:'M0 0 L4 0 L4 2 L0 2 Z'});"
        "const wbSketchData=(s)=>JSON.parse(s.data);"
        "const wbPathBBox=(d)=>{const n=d.match(/-?\\d+(?:\\.\\d+)?/g).map(Number);const xs=n.filter((_,i)=>i%2==0),ys=n.filter((_,i)=>i%2==1);return{minX:Math.min(...xs),maxX:Math.max(...xs),minY:Math.min(...ys),maxY:Math.max(...ys)};};"
        "const wbTransformPathD=(d,o)=>{const n=d.match(/-?\\d+(?:\\.\\d+)?/g).map(Number);const out=[];for(let i=0;i<n.length;i+=2)out.push((o.anchorX+(n[i]-o.anchorX)*o.sx+o.dx)+' '+(o.anchorY+(n[i+1]-o.anchorY)*o.sy+o.dy));return 'M'+out.join(' L')+' Z';};"
        "const wbRecordGesture=async(f)=>{gestures++;await f();};const wbSaveMany=async()=>{saved++;};"
        "const toast=()=>{},wbScheduleRender=()=>{},wbAnnounce=()=>{},nounCount=()=>'',document={querySelector:()=>null};"
        + body
        + "wbStickerSwap().then(()=>{const A=JSON.parse(a.data),B=JSON.parse(b.data);"
        "console.log(JSON.stringify({gestures,saved,a:[A.icon,A.fill,A.opacity,A.library_ref,wbPathBBox(A.d)],b:[B.icon,B.fill,wbPathBBox(B.d)]}));});"
    )
    out = json.loads(subprocess.run([node, "-e", code], capture_output=True, text=True, check=True).stdout)
    assert out["gestures"] == 1 and out["saved"] == 1
    assert out["a"][:4] == ["heart", "#f00", 0.5, "icons/heart"]
    # heart is 2:1; each copy's square box holds it at the largest uniform scale, centred.
    assert out["a"][4] == {"minX": 10, "maxX": 30, "minY": 15, "maxY": 25}
    assert out["b"][:2] == ["heart", "#0a0"] and out["b"][2]["minX"] == 100 and out["b"][2]["maxX"] == 200
