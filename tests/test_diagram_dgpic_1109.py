"""INBOX 1661 (l), the part dgml-1109 left: a mind map and a timeline edited on their picture (a press picks a part, a
double press renames it there, a drag reorders or nests it). Mermaid's SVG for those kinds carries no row ids, but it
numbers its boxes in the order it read them; diagram-tree-canvas.js matches the N-th box to the N-th row and checks the
words, so two parts with the same name still land on their own rows. The two SVGs are Mermaid 12.2's own output, trimmed
(styles, arrows and edges taken out). Measured in the app: docs/roadmap/agent-remaining/dgpic-1109.md."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
TESTS = ROOT / "tests"
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="node is not installed")

MM_SVG = (TESTS / "diagram_mindmap_dgpic.svg").read_text(encoding="utf-8")
TL_SVG = (TESTS / "diagram_timeline_dgpic.svg").read_text(encoding="utf-8")
MM = 'mindmap\n  root((Plan))\n    Alpha\n      Leaf one\n      Same\n    Beta\n      Same\n    Gamma["Box & <b>"]\n'
TL = "timeline\n  title T\n  2019 : zero\n  section Early\n    2020 : one : uno\n    2021 : two\n  section Late\n    2022 : one\n"


def _js(name: str) -> str:
    return (JS / name).read_text(encoding="utf-8")


def _run(expr: str, **values):
    run = (
        "const vm=require('vm');const ctx={diagramModel:{decode:(t)=>t,statements:(t)=>t.split('\\n').map((l)=>l.trim()).filter(Boolean),"
        "front:(t)=>({front:[],rest:t})}};vm.createContext(ctx);"
        f"vm.runInContext(require('fs').readFileSync({json.dumps(str(JS / 'diagram-kinds.js'))},'utf8'),ctx);"
        f"vm.runInContext(require('fs').readFileSync({json.dumps(str(JS / 'diagram-tree-canvas.js'))},'utf8'),ctx);"
        "const K=ctx.diagramModel.kinds,C=ctx.diagramModel.treeCanvas,V=" + json.dumps(values) + ";"
        "const name=(A,m,k)=>A.text(K.ops.find(A,m,k).node);"
        f"process.stdout.write(JSON.stringify({expr}));"
    )
    return json.loads(subprocess.run(["node", "-e", run], capture_output=True, text=True, check=True).stdout)


@needs_node
def test_every_mind_map_box_is_its_own_row_even_when_two_share_a_name():
    out = _run(
        "(()=>{const A=K.mindmap,m=A.parse(V.src);const hit=C.boxes(V.svg,A,m,K.ops.key);"
        "const rows=[];K.ops.walk(A,m,(n)=>rows.push(K.ops.key(n)));"
        "const same=hit.boxes.filter((b)=>name(A,m,b.id)==='Same').map((b)=>K.ops.find(A,m,b.id).parent.text);"
        "return {rows:rows.length,keys:hit.boxes.map((b)=>b.id),order:rows,same,root:hit.boxes[0],vb:hit.vb}})()",
        src=MM, svg=MM_SVG,
    )
    assert out["rows"] == 7 and out["keys"] == out["order"]  # Box N is row N, in the order the source prints
    assert out["same"] == ["Alpha", "Beta"]  # the two "Same" leaves are under their own parents
    assert out["vb"] == [5, 5, 363.05, 378.58]
    root = out["root"]
    assert (root["x"], root["y"]) == (116.25, 198.7) and root["w"] >= 58 and root["h"] >= 58  # the circle, r 29.09


@needs_node
def test_a_box_whose_words_are_not_its_rows_is_left_out_not_given_to_the_wrong_row():
    # A drawing a step behind the model (a part renamed, not yet redrawn) must not pick a neighbour.
    out = _run(
        "(()=>{const A=K.mindmap,m=A.parse(V.src);m.root.children[1].text='Renamed';"
        "const hit=C.boxes(V.svg,A,m,K.ops.key);return {n:hit.boxes.length,names:hit.boxes.map((b)=>name(A,m,b.id))}})()",
        src=MM, svg=MM_SVG,
    )
    assert out["n"] == 6 and "Renamed" not in out["names"] and out["names"].count("Same") == 2


@needs_node
def test_a_timeline_box_is_its_row_and_a_period_mermaid_does_not_draw_is_left_out():
    # Mermaid draws only the sections when there are any: "2019 : zero", before the first section, is not on the picture.
    out = _run(
        "(()=>{const A=K.timeline,m=A.parse(V.src);const hit=C.boxes(V.svg,A,m,K.ops.key);"
        "return {names:hit.boxes.map((b)=>name(A,m,b.id)),types:hit.boxes.map((b)=>b.et),"
        "ones:hit.boxes.filter((b)=>name(A,m,b.id)==='one').map((b)=>K.ops.find(A,m,b.id).parent.when),first:hit.boxes[0]}})()",
        src=TL, svg=TL_SVG,
    )
    assert out["names"] == ["Early", "2020", "one", "uno", "2021", "two", "Late", "2022", "one"]
    assert out["types"][:3] == ["s", "p", "e"]
    assert out["ones"] == ["2020", "2022"]
    first = out["first"]
    assert (first["x"], round(first["y"], 1), first["w"]) == (395, 84.4, 390)  # the section's band: x 200 to 590, y 50 to 118.8


@needs_node
def test_a_drop_on_a_part_goes_before_it_after_it_or_into_it_by_where_the_pointer_is():
    out = _run(
        "(()=>{const A=K.mindmap,m=A.parse(V.src);const hit=C.boxes(V.svg,A,m,K.ops.key);"
        "const by=(t)=>hit.boxes.find((b)=>name(A,m,b.id)===t);const [alpha,beta,gamma,plan]=['Alpha','Beta','Box & <b>','Plan'].map(by);"
        "const at=(b,f)=>[b.x-b.w/2+b.w*f,b.y];const say=(s)=>s&&[s.op,s.parent?A.text(s.parent):null,s.before?A.text(s.before):null];"
        "const t=(b,f,k)=>say(C.spot(A,m,hit,...at(b,f),'b',k));"
        "const moved=(()=>{const s=C.spot(A,m,hit,...at(alpha,0.1),'b',gamma.id);"
        "K.ops.move(A,m,gamma.id,s.parent?K.ops.key(s.parent):null,s.before?K.ops.key(s.before):null);return m.root.children.map((n)=>n.text)})();"
        "return {left:t(beta,0.1,gamma.id),right:t(beta,0.9,gamma.id),mid:t(beta,0.5,gamma.id),root:t(plan,0.1,gamma.id),"
        "self:t(alpha,0.5,alpha.id),child:t(by('Leaf one'),0.5,alpha.id),moved}})()",
        src=MM, svg=MM_SVG,
    )
    assert out["left"] == ["before", "Plan", "Beta"]
    assert out["right"] == ["after", "Plan", None]  # Box is the one dragged: after Beta is the end
    assert out["mid"] == ["into", "Beta", None]
    assert out["root"] == ["into", "Plan", None]  # the central idea holds, never has a sister
    assert out["self"] is None and out["child"] is None  # not onto itself, not into its own branch
    assert out["moved"] == ["Box & <b>", "Alpha", "Beta"]


@needs_node
def test_on_a_timeline_an_event_goes_into_a_period_and_periods_reorder_side_by_side():
    out = _run(
        "(()=>{const A=K.timeline,m=A.parse(V.src);const hit=C.boxes(V.svg,A,m,K.ops.key);"
        "const by=(t)=>hit.boxes.find((b)=>name(A,m,b.id)===t);const say=(s)=>s&&[s.op,s.parent?A.text(s.parent):null,s.before?A.text(s.before):null];"
        "const p20=by('2020'),p21=by('2021'),uno=by('uno'),two=by('two'),late=by('Late');"
        "return {event:say(C.spot(A,m,hit,p21.x,p21.y,'e',uno.id)),"
        "above:say(C.spot(A,m,hit,uno.x,uno.y-uno.h*0.4,'e',two.id)),"
        "period:say(C.spot(A,m,hit,p20.x-p20.w*0.4,p20.y,'p',p21.id)),"
        "section:say(C.spot(A,m,hit,late.x,late.y,'p',p21.id)),wrong:say(C.spot(A,m,hit,p20.x,p20.y,'s',late.id))}})()",
        src=TL, svg=TL_SVG,
    )
    assert out["event"] == ["into", "2021", None]
    assert out["above"] == ["before", "2020", "uno"]  # events stack down a period: the upper part is before
    assert out["period"] == ["before", "Early", "2020"]
    assert out["section"] == ["into", "Late", None]
    assert out["wrong"] is None  # a section has no place in a period


def test_the_picture_of_every_kind_is_wired_through_one_lazy_file_and_the_overlay():
    builder = _js("diagram-builder.js")
    assert 'S?.k && (await lazyScript("/js/diagram-seq-canvas.js"))' in builder and "(!S.k || S.hitAt)" in builder
    assert "(S.k && !S.hitAt)" in _js("diagram-overlay.js")
    seq = _js("diagram-seq-canvas.js")
    assert 'lazyScript("/js/diagram-tree-canvas.js")' in seq and "function edit(S, read" in seq
    tree = _js("diagram-tree-canvas.js")
    assert "diagramModel.seqCanvas.edit(S, " in tree and "diagramModel.treeCanvas = {" in tree


def test_a_press_on_a_drawn_part_starts_the_lists_drag_and_a_drop_on_one_names_its_place():
    kinds = _js("diagram-kinds.js")
    seed = kinds.split("function seedBlock(event)")[1].split("function pictureDrop(")[0]
    assert "diagramModel.treeCanvas?.node(event, panes)" in seed
    drop = kinds.split("function dropAt(g)")[1].split("const withinNode")[0]
    assert "diagramModel.treeCanvas?.over(g)" in drop


def test_the_guide_says_a_mind_map_and_a_timeline_picture_take_a_press_a_rename_and_a_drag():
    from tessellate.ai.help_chat import HELP_TOPICS

    body = str(next(t["body"] for t in HELP_TOPICS if t["id"] == "diagram-kinds"))
    assert "On a sequence, mind map or timeline picture a press picks a part" in body
    assert "a mind map or timeline part dragged onto another lands before, after or in it" in body
