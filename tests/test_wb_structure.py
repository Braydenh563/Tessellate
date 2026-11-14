"""Structure rows of the board (WHITEBOARD_PLAN section 12): tags and a tag filter, collapsing a frame, the drop
highlight on a frame, and find limited to one frame (`scratchpad/ui-sweeps/wbstructure3.js`, 33/33)."""

from __future__ import annotations

from tests._app_js import frontend_text
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from pydantic import ValidationError

from tessellate.api.routes_whiteboard import WhiteboardObjectData
from tessellate.api.wb_model import MAX_TAG_CHARS, MAX_TAGS_PER_ITEM, check_sketch_data

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
STRUCT = (JS / "whiteboard-structure-more.js").read_text(encoding="utf-8")
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "css" / "library-lazy.css").read_text(encoding="utf-8")
WB = frontend_text("whiteboard.js")
CMDS = (JS / "whiteboard-commands.js").read_text(encoding="utf-8")


def test_an_item_takes_a_bounded_list_of_tags():
    assert WhiteboardObjectData(tags=["a", "b"]).tags == ["a", "b"]
    with pytest.raises(ValidationError):
        WhiteboardObjectData(tags=["x"] * (MAX_TAGS_PER_ITEM + 1))
    with pytest.raises(ValidationError):
        WhiteboardObjectData(tags=["x" * (MAX_TAG_CHARS + 1)])
    with pytest.raises(ValidationError):
        WhiteboardObjectData(tags=[""])


def test_a_folded_frame_keeps_its_height_within_the_object_bounds():
    assert WhiteboardObjectData(collapsed=True, fold_h=300).fold_h == 300
    for bad in (19, 4001):
        with pytest.raises(ValidationError):
            WhiteboardObjectData(fold_h=bad)


def test_a_drawing_refuses_bad_tags_too():
    check_sketch_data(json.dumps({"tags": ["ok"]}))
    with pytest.raises(Exception):
        check_sketch_data(json.dumps({"tags": ["x"] * (MAX_TAGS_PER_ITEM + 1)}))
    with pytest.raises(Exception):
        check_sketch_data(json.dumps({"tags": "nope"}))


def test_typed_tags_are_split_trimmed_and_not_repeated():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    a = STRUCT.index("  function parseTags")
    fn = STRUCT[a : STRUCT.index("\n  }\n", a) + 4]
    script = "const MAX_TAG = 40, MAX_TAGS = 20;\n" + fn + 'console.log(JSON.stringify([parseTags("b, a;  B\\n c  d,,"), parseTags(""), parseTags("x".repeat(60)).map((t) => t.length)]));'
    got = json.loads(subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=30, check=True).stdout)
    assert got == [["b", "a", "c d"], [], [40]]


def test_the_view_rule_hides_folded_children_in_one_place():
    # Export, present, Select all and find all read wbItemHidden, so the fold needs no code of their own.
    hidden = WB[WB.index("function wbItemHidden") :]
    assert "wbFmtState.structure?.folded(kind, item)" in hidden[:900]
    assert "fold_h" in STRUCT and "wbRecordGesture" in STRUCT
    assert "wb-frame-collapsed" in STRUCT and "wb-frame-collapsed" in CSS


def test_find_and_replace_all_respect_the_frame_scope():
    assert WB.count("wbFmtState.structure?.scope()") >= 2
    assert "wbFmtState.structure?.searchControls(bar)" in WB
    assert "wbFmtState.structure?.closeSearch()" in WB
    assert "wb-search-frame" in STRUCT


def test_the_commands_and_controls_exist():
    for cmd in ("collapse-frame", "expand-frame", "edit-tags", "filter-tag", "find-in-frame"):
        assert f'id: "{cmd}"' in CMDS
    for ident in ("wb-fmt-tags", "wb-fmt-tag-input", "wb-fmt-collapse"):
        assert f'id="{ident}"' in HTML
    assert 'data-fmt="tags"' in HTML and 'data-fmt="collapse"' in HTML


def test_the_drop_highlight_is_a_token_coloured_outline_without_blur():
    rule = re.search(r"\.wb-object-frame\.wb-drop-target \{([^}]*)\}", CSS)
    assert rule and "var(--accent)" in rule.group(1) and "blur" not in rule.group(1)
    assert "wb-drop-target" in STRUCT


def test_the_filter_dims_without_taking_the_pointer():
    rule = re.search(r"#whiteboard-container \.wb-tag-dim \{([^}]*)\}", CSS)
    assert rule and "opacity" in rule.group(1) and "pointer-events" not in rule.group(1)


def test_the_layers_tab_calls_a_folded_childs_row_folded_not_hidden_l_whiteboard_26():
    lib = (JS / "whiteboard-library.js").read_text(encoding="utf-8")
    assert "foldedBy" in STRUCT and "wbItemHidden(row.kind, row.item, { ignoreFold: true })" in lib
    assert "Expand the frame to see it." in lib and "is-folded" in lib
    # The eye must not write hidden=false for a fold: it names the frame instead.
    toggle = lib[lib.index("async function wbLayerToggleHidden") :]
    assert toggle.index("structure?.foldFrame") < toggle.index("wbSetHidden")
