"""Rainbow every level (F3, MINDMAP_PLAN gap 10): the canvas's `wbMapColors` and
the thumbnail's `_map_branch_colors` pick the same colour for every topic."""

from tests._app_js import frontend_text
import json
import shutil
import subprocess

import pytest

from tessellate.api.wb_preview import MAP_BRANCH_PALETTE, _map_branch_colors

MAP = frontend_text("whiteboard-map.js")


def _fn(name):
    rest = MAP[MAP.index(f"function {name}(") :]
    return rest[: rest.index("\n}\n") + 3]


def _canvas(parents, rainbow, own=None):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    ids = sorted(parents)
    script = (
        _fn("wbMapColors")
        + f"const P={json.dumps(MAP_BRANCH_PALETTE)};const wbMapPalette=()=>P;"
        + f"const wbMapTheme=()=>({json.dumps({'rainbow': True} if rainbow else {})});"
        + f"const par={json.dumps({str(k): v for k, v in parents.items()})};const own={json.dumps({str(k): v for k, v in (own or {}).items()})};"
        + f"const nodes={json.dumps(ids)}.map(id=>({{id,data:own[id]?{{color:own[id]}}:{{}}}}));"
        + "const childrenOf=new Map(nodes.map(n=>[n.id,[]]));const roots=[];"
        + "for(const n of nodes){const p=par[n.id];if(p==null)roots.push(n);else childrenOf.get(p).push(n);}"
        + "const out={};for(const [k,v] of wbMapColors({nodes,roots,childrenOf}))out[k]=v;"
        + "console.log(JSON.stringify(out));"
    )
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, check=True).stdout
    return {int(k): v for k, v in json.loads(out).items()}


@pytest.mark.parametrize("rainbow", [False, True])
def test_canvas_and_thumbnail_agree(rainbow):
    parents = {1: None, 2: 1, 3: 1, 4: 2, 5: 2, 6: 2, 7: 4, 8: 3, 9: 8}
    own = {6: "#abcdef"}
    server = _map_branch_colors(parents, own, None, rainbow=rainbow)
    assert {k: v for k, v in _canvas(parents, rainbow, own).items() if v} == server


def test_rainbow_changes_the_third_level_and_off_does_not():
    parents = {1: None, 2: 1, 4: 2, 5: 2, 7: 4}
    off = _canvas(parents, False)
    on = _canvas(parents, True)
    assert off[4] == off[2] == off[7]
    assert on[4] != on[5] and on[7] != on[4] and on[2] == off[2]


def test_the_map_dialog_offers_it_as_a_check_in_the_whole_map_group():
    assert '{ key: "rainbow", label: "Colour every level", kind: "check" }' in MAP
    assert '"rainbow", "legend"]);' in MAP  # never merged onto a topic (WB_MAP_THEME_META)


@pytest.mark.parametrize("rainbow", [False, True])
def test_a_topic_still_waiting_for_its_id_is_the_newest_branch(rainbow):
    """L-mindmap-13 (2026-11-13): a topic added before the server answers holds
    a negative provisional id, and by that id it was the oldest branch on the
    map: Tab on the root moved every later branch one colour along (41 of 41
    topics repainted on a 41-topic map) until the real id came back."""
    parents = {1: None, 2: 1, 3: 1, 4: 1, 5: 2}
    before = _canvas(parents, rainbow)
    after = _canvas({**parents, -1: 1, -2: None}, rainbow)
    for node in parents:
        assert after[node] == before[node], node
    assert after[-1] == _canvas({**parents, 9: 1}, rainbow)[9]
