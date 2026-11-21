"""A legend for markers and colours, drawn on the map (MINDMAP_PLAN gap 11): a
map-level theme switch, listing the main branches' colours and only the markers
the map uses."""

from tests._app_js import frontend_text
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tessellate.api.wb_board import _clean_theme
from tessellate.api.wb_model import MAP_LEVEL_THEME_FIELDS

ROOT = Path(__file__).resolve().parents[1]
MAP = frontend_text("whiteboard-map.js")


def test_legend_is_a_map_level_boolean_theme_field():
    assert _clean_theme({"legend": True}) == {"legend": True}
    assert _clean_theme({"legend": False}) == {}
    assert "legend" in MAP_LEVEL_THEME_FIELDS
    assert '{ key: "legend", label: "Show a legend", kind: "check" }' in MAP
    assert '"legend"]);' in MAP  # WB_MAP_THEME_META: never merged onto a topic


def test_the_legend_lists_branches_and_only_the_markers_in_use():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    start = MAP.index("function wbRenderMapLegend(")
    body = MAP[start : MAP.index("\n}\n", start) + 3]
    # Run the real renderer against a tiny fake DOM and map.
    script = (
        "const made=[];"
        "const mk=(tag)=>({tag,children:[],dataset:{},className:'',setAttribute(){},removeAttribute(){},style:{},"
        "append(...c){this.children.push(...c)},appendChild(c){this.children.push(c)},replaceChildren(...c){this.children=c}});"
        "const box=mk('div');"
        "const document={getElementById:()=>box,createElement:mk};"
        "const wbMapPerspective=()=>'branch';const wbMapTheme=()=>({legend:true});const wbIsMap=()=>true;"
        "const wbMapFacets=()=>new Map();const wbMapPalette=()=>['#1','#2'];const wbMapQuietColour=()=>'#q';"
        "const WB_MAP_MARKER_ICON_NAMES=new Map([['star','Star']]);const WB_MAP_PERSPECTIVES=[];const WB_MAP_AGE_BUCKETS=[];"
        "const wbMapLabel=(n)=>n.data.content;"
        "const wbMapMarkerParts=(d)=>({priority:d.priority??null,progress:null,flag:!!d.flag,icons:d.markers||[]});"
        "const painted=[];const wbMapPaintMarkers=(h,d)=>painted.push(d);"
        "const wbMapColors=()=>new Map([[2,'#1'],[3,'#2']]);"
        "const nodes=[{id:1,parent_id:null,data:{content:'Root'}},{id:2,parent_id:1,data:{content:'North',markers:['star']}},"
        "{id:3,parent_id:1,data:{content:'South',priority:2}},{id:4,parent_id:2,data:{content:'Deep',flag:true}}];"
        "const byId=new Map(nodes.map(n=>[n.id,n]));"
        + body
        + "wbRenderMapLegend({nodes,byId});"
        "const rows=box.children[1].children.map(r=>r.children[1].textContent);"
        "console.log(JSON.stringify({hidden:box.hidden,own:box.dataset.own,rows,painted}));"
    )
    out = json.loads(subprocess.run([node, "-e", script], capture_output=True, text=True, check=True).stdout)
    assert out["hidden"] is False and out["own"] == "1"
    assert out["rows"] == ["North", "South", "Priority, 1 is first", "Flagged", "Star"]
    assert {"priority": 1} in out["painted"] and {"markers": ["star"]} in out["painted"]
    assert not any("progress" in p for p in out["painted"])


def test_without_the_switch_a_branch_view_draws_no_legend():
    assert "perspective === \"branch\" && !own" in MAP
