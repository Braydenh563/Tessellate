"""INBOX 715: the New board dialog, and the board and mind map templates.

The owner, with the dialog on screen: "name text clashes with border. also
the pill at the top is ugly and I want it to be redesigned to be like the
other popups. also there are no mindmap templates to choose from"; then, of
the SWOT, retro and Kanban templates: "some of the templates are poorly
designed and the templates need massive improving and expanding"; then, of
the Library's map tiles, "these all look the same".

The template files are the one source the dialog, the Library's tiles and a
new map's offer all read, so the rules are held on the files and on the two
picture functions (run under node), and the dialog's shape on index.html.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tessellate.api.routes_whiteboard import BOARD_LAYOUTS, MAP_BRANCH_PALETTE

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "frontend" / "board-library"
JS = ROOT / "frontend" / "js"
PURPOSES = {"plan", "decide", "solve", "meet", "learn"}
TINTS = {"neutral", "red", "amber", "green", "teal", "blue", "violet", "pink"}
SHAPES = {"radial", "two-sided", "fishbone", "fork", "phases", "tiers", "tree"}
#: The frame's header: where its title and hint sit, inside its top.
HEADER = 96


def _set(name: str) -> list[dict]:
    return json.loads((LIB / f"{name}.json").read_text(encoding="utf-8"))["items"]


def _frames(entry: dict) -> list[dict]:
    return [i for i in entry["payload"]["items"] if i["kind"] == "object" and i["type"] == "frame"]


def _copy_ok(text: str) -> bool:
    return bool(text) and (text[0].isupper() or text[0].isdigit()) and chr(0x2014) not in text and "!" not in text and "Oops" not in text


def test_board_templates_are_many_grouped_and_described():
    boards = _set("templates")
    keys = {b["key"] for b in boards}
    assert len(boards) >= 16
    # The ones the owner's list named, beyond the five there were.
    assert {"eisenhower", "week", "brief", "journey", "lean", "pros-cons", "mood", "cornell",
            "meeting", "okrs", "five-whys", "fishbone", "swot"} <= keys
    for b in boards:
        assert b["template"] == "board" and b["kind"] == "element", b["key"]
        assert b["purpose"] in PURPOSES, b["key"]
        assert _copy_ok(b["name"]) and _copy_ok(b["hint"]), b["key"]
        assert len(b["hint"]) <= 60, b["key"]
    # Every group the picker draws has something in it.
    assert {b["purpose"] for b in boards} == PURPOSES


def test_every_template_frame_is_a_panel_with_a_title_and_a_hint():
    for b in _set("templates"):
        for f in _frames(b):
            d = f["data"]
            assert d.get("tint") in TINTS, (b["key"], d)
            assert _copy_ok(d["content"]) and len(d["content"]) <= 24, (b["key"], d)
            assert _copy_ok(d.get("hint", "")) and len(d["hint"]) <= 48, (b["key"], d)


def _overlap(a0, a1, b0, b1) -> bool:
    return min(a1, b1) - max(a0, b0) > 0


def test_frames_never_overlap_and_their_gutters_are_even():
    for b in _set("templates"):
        frames = _frames(b)
        gaps_x, gaps_y = set(), set()
        for i, f in enumerate(frames):
            for g in frames[i + 1 :]:
                fx = (f["x"], f["x"] + f["w"])
                gx = (g["x"], g["x"] + g["w"])
                fy = (f["y"], f["y"] + f["h"])
                gy = (g["y"], g["y"] + g["h"])
                assert not (_overlap(*fx, *gx) and _overlap(*fy, *gy)), (b["key"], f["data"], g["data"])
                if _overlap(*fy, *gy):
                    gaps_x.add(max(g["x"] - fx[1], f["x"] - gx[1]))
                if _overlap(*fx, *gx):
                    gaps_y.add(max(g["y"] - fy[1], f["y"] - gy[1]))
        # Neighbours only: the smallest gap on each axis is the gutter, and
        # every gap is that gutter or a whole frame and more beyond it.
        for gaps in (gaps_x, gaps_y):
            if gaps:
                assert min(gaps) in (40, 80), (b["key"], sorted(gaps))


def test_nothing_sits_in_a_frames_header():
    """A sticky or a drawing placed in a frame starts under its title and hint."""
    for b in _set("templates"):
        frames = _frames(b)
        for item in b["payload"]["items"]:
            if item["kind"] != "object" or item["type"] == "frame":
                continue
            for f in frames:
                inside = f["x"] <= item["x"] < f["x"] + f["w"] and f["y"] <= item["y"] < f["y"] + f["h"]
                if inside:
                    assert item["y"] >= f["y"] + HEADER, (b["key"], item["data"], f["data"])
                    assert item["y"] + item["h"] <= f["y"] + f["h"], (b["key"], item["data"])
                    assert item["x"] + item["w"] <= f["x"] + f["w"], (b["key"], item["data"])


def test_map_templates_are_many_and_each_says_how_it_is_drawn():
    maps = _set("maps")
    assert len(maps) >= 14
    assert {"brainstorm", "project", "book", "study", "decision", "swot", "goal", "weekly-review",
            "pros-cons", "meeting", "causes"} <= {m["key"] for m in maps}
    for m in maps:
        assert m["template"] == "map" and m["kind"] == "branch", m["key"]
        assert m["purpose"] in PURPOSES and m["shape"] in SHAPES and m["layout"] in BOARD_LAYOUTS, m["key"]
        assert _copy_ok(m["name"]) and _copy_ok(m["hint"]), m["key"]
        nodes = m["payload"]["nodes"]
        assert len(nodes) >= 2 and any(n["children"] for n in nodes), m["key"]


def _node(source: str, names: list[str], call: str) -> str:
    bodies = []
    for name in names:
        match = re.search(rf"^function {name}\(.*?^\}}", source, re.S | re.M)
        assert match, f"{name} is gone from whiteboard-templates.js"
        bodies.append(match.group(0))
    script = "\n".join(bodies) + f"\nprocess.stdout.write(JSON.stringify({call}));"
    return subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_no_two_map_pictures_are_the_same():
    """The owner: "these all look the same". Every picture is drawn from its
    template's own tree and shape, so no two produce the same drawing."""
    source = (JS / "whiteboard-templates.js").read_text(encoding="utf-8")
    maps = _set("maps")
    out = json.loads(_node(source, ["wbThumbRound", "wbThumbLook", "wbThumbShapePart", "wbMapThumbSpec"], f"{json.dumps(maps)}.map((m) => wbMapThumbSpec(m))"))
    drawn = [json.dumps(spec["parts"]) for spec in out]
    assert len(set(drawn)) == len(drawn), [m["key"] for m, d in zip(maps, drawn) if drawn.count(d) > 1]
    # And the shapes are the ones asked for: a fishbone's spine, a radial's
    # spokes from the centre, a two-sided map's branches on both sides.
    by_key = {m["key"]: spec for m, spec in zip(maps, out)}
    paths = lambda k: [p["a"]["d"] for p in by_key[k]["parts"] if p["tag"] == "path"]  # noqa: E731
    assert "M 3 20 L 49 20" in paths("causes")
    assert sum(d.startswith("M 32 20 L") for d in paths("brainstorm")) == 4
    xs = [p["a"]["x"] for p in by_key["pros-cons"]["parts"] if "wb-thumb-node" in p["cls"].split()]
    assert min(xs) < 32 < max(xs)


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_a_map_pictures_branches_wear_their_own_colours():
    """The library's map tiles were one grey. Each branch's line, box and leaves
    take the classic palette's colour by creation order (`wb-thumb-bN`); the
    root and the labels stay neutral; the colours live in library-lazy.css."""
    source = (JS / "whiteboard-templates.js").read_text(encoding="utf-8")
    maps = _set("maps")
    out = json.loads(_node(source, ["wbThumbRound", "wbThumbLook", "wbThumbShapePart", "wbMapThumbSpec"], f"{json.dumps(maps)}.map((m) => wbMapThumbSpec(m))"))
    for entry, spec in zip(maps, out):
        tones = {c for p in spec["parts"] for c in p["cls"].split() if re.fullmatch(r"wb-thumb-b\d", c)}
        branches = len(entry.get("payload", {}).get("nodes", []))
        if branches > 1 or len(tones) > 1:
            assert len(tones) >= 2, (entry["key"], tones)
        for p in spec["parts"]:
            if "wb-thumb-root" in p["cls"] or "wb-thumb-label" in p["cls"]:
                assert "wb-thumb-b" not in p["cls"], (entry["key"], p["cls"])
    css = (JS.parent / "css" / "library-lazy.css").read_text(encoding="utf-8")
    for i, hexcode in enumerate(MAP_BRANCH_PALETTE):
        assert re.search(rf"\.wb-thumb-b{i} \{{\s*--thumb-b: {hexcode};", css), i


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_one_title_size_per_board_picture_inside_its_frame():
    """The screenshots had titles of three sizes sitting on dashed borders:
    each picture now draws every frame title at one size, inside the frame
    with the panel's padding, and frames are solid (no dash)."""
    source = (JS / "whiteboard-templates.js").read_text(encoding="utf-8")
    boards = _set("templates")
    payloads = json.dumps([b["payload"] for b in boards])
    out = json.loads(_node(source, ["wbThumbRound", "wbBoardThumbSpec"], f"{payloads}.map((p) => wbBoardThumbSpec(p))"))
    for b, spec in zip(boards, out):
        titles = [p for p in spec["parts"] if p["cls"] == "wb-thumb-title"]
        frames = [p for p in spec["parts"] if p["cls"] == "wb-thumb-frame"]
        assert len(titles) == len(frames) == len(_frames(b)), b["key"]
        assert len({t["a"]["font-size"] for t in titles}) <= 1, b["key"]
        for t, f in zip(titles, frames):
            size = t["a"]["font-size"]
            assert t["a"]["x"] >= f["a"]["x"] + 16, b["key"]
            assert t["a"]["y"] - size >= f["a"]["y"] + 8, b["key"]
            # The estimated width of the words stays inside the frame.
            assert t["a"]["x"] + 0.6 * size * len(t["text"]) <= f["a"]["x"] + f["a"]["width"], (b["key"], t["text"])
        assert not any("stroke-dasharray" in p["a"] for p in spec["parts"]), b["key"]


def test_the_dialog_chooses_its_kind_with_a_tab_strip_and_groups_its_rows():
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    dialog = html[html.index('<dialog id="wb-template-dialog"') :]
    dialog = dialog[: dialog.index("</dialog>")]
    assert 'class="seg' not in dialog
    strip = re.search(r'<div class="tabs-line popup-kinds[^"]*" id="wb-template-kind" role="tablist"', dialog)
    assert strip, "the kind is a .tabs-line tab strip"
    assert dialog.count('role="tab"') == 2 and 'aria-selected="true"' in dialog
    # The strip comes straight after the head, before the name.
    assert dialog.index('id="wb-template-kind"') < dialog.index('id="wb-template-name"')
    js = (JS / "whiteboard-templates.js").read_text(encoding="utf-8")
    gallery = js[js.index("async function wbOpenTemplateGallery") :]
    assert "WB_TEMPLATE_PURPOSES" in gallery and "wb-template-group" in gallery
    assert "wbTemplatePicture(choice, kind)" in gallery
    assert '"ArrowLeft", "ArrowRight", "Home", "End"' in gallery
    # The name field's word clears the field's focus ring by --space-2.
    css = (ROOT / "frontend" / "css" / "07-whiteboard-misc.css").read_text(encoding="utf-8")
    rule = css[css.index(".space-dialog label.wb-template-name-row {") :]
    rule = rule[: rule.index("}")]
    assert "display: grid" in rule and "gap: calc(var(--space-2) + var(--ring-room))" in rule
    lazy = (ROOT / "frontend" / "css" / "library-lazy.css").read_text(encoding="utf-8")
    text = lazy[lazy.index(".wb-template-preview-text {") :]
    assert "padding: var(--space-3)" in text[: text.index("}")]


def test_a_new_maps_offer_and_the_tiles_draw_from_the_one_list():
    """The "Start from a shape" bar had four templates of its own; it reads
    the Library's map templates now, and draws each with the same picture."""
    map_js = (JS / "whiteboard-map.js").read_text(encoding="utf-8")
    assert "WB_MAP_TEMPLATES" not in map_js
    js = (JS / "whiteboard-templates.js").read_text(encoding="utf-8")
    offer = js[js.index("function wbRenderMapTemplates") :]
    assert 'wbLibSets.get("maps")' in offer and "wbThumbSvg(wbMapThumbSpec(entry))" in offer
    lib = (JS / "whiteboard-library.js").read_text(encoding="utf-8")
    thumb = lib[lib.index("function wbLibThumb") :]
    assert "wbMapThumbSpec(entry)" in thumb[: thumb.index("\n}\n")]
    lazy = (ROOT / "frontend" / "css" / "library-lazy.css").read_text(encoding="utf-8")
    name = lazy[lazy.index(".wb-lib-name {") :]
    name = name[: name.index("}")]
    assert "white-space: nowrap" in name and "text-overflow: ellipsis" in name


def test_a_new_map_from_a_template_takes_its_layout_and_its_name(ai_client):
    out = ai_client.post("/board-library/new-board", json={"builtin": "maps/causes", "name": "Late deliveries"})
    assert out.status_code == 201, out.text
    assert out.json()["layout"] == "tree-left"
    objects = ai_client.get(f"/whiteboard/?board_id={out.json()['id']}").json()["objects"]
    roots = [o for o in objects if o["parent_id"] is None]
    assert [o["data"]["content"] for o in roots] == ["Late deliveries"]


def test_a_template_frame_keeps_its_tint_and_hint(ai_client):
    out = ai_client.post("/board-library/new-board", json={"builtin": "templates/swot", "name": "Plan B"})
    assert out.status_code == 201, out.text
    frames = [o for o in ai_client.get(f"/whiteboard/?board_id={out.json()['id']}").json()["objects"] if o["kind"] == "frame"]
    assert {f["data"]["content"]: f["data"]["tint"] for f in frames} == {
        "Strengths": "green", "Weaknesses": "red", "Opportunities": "blue", "Threats": "amber",
    }
    assert all(f["data"]["hint"] for f in frames)
