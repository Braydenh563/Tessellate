"""INBOX 792: "there is only one actual arrow option for the links", and the
Start and End lists were eleven words long with no picture.

The renderer draws the plain ends open (`arrow`, `bar`, `circle`, `square`,
`multiline`) or closed (`triangle`, `diamond`, `diamond-filled`; a solid end is
a closed outline with smaller copies of itself inside, so it stays one more
subpath of the shaft's `d`). The lists group the plain and the
entity-relationship ends and every row leads with a drawing of its end, which
is the renderer's own path as a mask: this runs the renderer and checks each
drawing against it, so the picture cannot drift from what lands on the board.
"""

import json
import re
import shutil
import subprocess
import urllib.parse
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")
INDEX = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
LAZY = (ROOT / "frontend" / "css" / "library-lazy.css").read_text(encoding="utf-8")


def _function(name: str) -> str:
    start = SOURCE.index(f"function {name}(")
    return SOURCE[start : SOURCE.index("\n}\n", start) + 3]


def _paths(tip_x=38, tip_y=8, angle=0, head=12) -> dict[str, str]:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    start = SOURCE.index("const WB_CAP_KINDS")
    head_src = SOURCE[start : SOURCE.index("function wbCapPath(", start)]
    script = (
        _function("wbArrowHeadPath") + head_src + _function("wbFilledTriangle") + _function("wbCapPathMore")
        + _function("wbCapPath")
        + f"console.log(JSON.stringify(WB_CAP_KINDS.map((k) => [k, wbCapPath(k, {tip_x}, {tip_y}, {angle}, {head})])));"
    )
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, check=True)
    return dict(json.loads(out.stdout.strip()))


def _round(path: str) -> str:
    return re.sub(r"-?\d+\.\d{3,}", lambda m: str(round(float(m.group()), 2)), path)


def test_every_end_the_renderer_draws_is_offered_with_a_drawing_of_it():
    paths = _paths()
    assert {"triangle", "diamond", "diamond-filled", "bar"} <= set(paths)
    for which in ("startcap", "endcap"):
        select = INDEX[INDEX.index(f'id="wb-prop-{which}"') :]
        select = select[: select.index("</select>")]
        assert '<optgroup label="Plain ends">' in select and '<optgroup label="Entity-relationship ends">' in select
        for kind in paths:
            assert f'value="{kind}" data-menu-class="wb-cap wb-cap-{kind}' in select, (which, kind)
    for kind, cap in paths.items():
        rule = re.search(rf"\.wb-cap-{re.escape(kind)} \{{\s*--wb-cap: url\(\"([^\"]+)\"\);", LAZY)
        assert rule, kind
        drawing = urllib.parse.unquote(rule.group(1))
        assert _round(cap) in drawing if cap else "M 3 8 L 38 8'" in drawing, kind


def test_a_solid_end_is_a_closed_outline_with_copies_inside_it():
    paths = _paths(head=12)
    assert paths["triangle"].count("Z") > 3 and paths["diamond-filled"].count("Z") > 2
    assert paths["diamond"].count("Z") == 1
    assert paths["bar"].count("M") == 1 and "Z" not in paths["bar"]
    # A heavier line has a longer head and takes fewer, wider steps.
    assert paths["triangle"].count("Z") >= _paths(head=30)["triangle"].count("Z")
    assert len(set(paths.values())) == len(paths), "two ends draw the same mark"


def test_the_rows_draw_the_example_in_the_ink_and_start_is_turned_round():
    row = re.search(r"\.wb-cap::before \{([^}]*)\}", LAZY)
    assert row and "background: currentColor" in row.group(1) and "mask: var(--wb-cap)" in row.group(1)
    assert re.search(r"\.wb-cap-start::before \{\s*transform: scaleX\(-1\);", LAZY)
    assert "#wb-prop-startcap ~ .select-opener .select-value::before" in LAZY
    fmt = (ROOT / "frontend" / "js" / "whiteboard-format.js").read_text(encoding="utf-8")
    assert "to.append(node.cloneNode(true))" in fmt, "the Format panel takes the bar's groups and drawings"


def test_the_owner_s_ends_are_all_offered_and_a_plain_line_takes_them():
    """2026-10-11, the owner: "can you add more shapes and more arrow options??"
    (the screenshot showed None, Open arrow and Filled triangle). Every end in
    the brief is a kind, a plain line shows the lists before it has an end,
    and the Line and Arrow tools choose the mark as well as which ends."""
    paths = _paths()
    for kind in ("none", "arrow", "triangle", "triangle-open", "circle", "circle-filled",
                 "diamond", "diamond-filled", "bar", "er-many"):
        assert kind in paths, kind
    assert paths["circle-filled"].count("Z") > 2 and paths["triangle-open"].count("Z") == 1
    assert "Many (crow's foot)" in INDEX
    assert '<select id="wb-arrow-head"' in INDEX and 'data-wb-tool-setting="head"' in INDEX
    assert re.search(r'line: \["size", "ends", "head", "dash"\]', SOURCE)
    takes = _function("wbSketchTakesCaps")
    assert 'parsed.shape === "line"' in takes and 'parsed.shape === "arrow"' in takes
    bar = SOURCE[SOURCE.index("function wbFillContextBar(") :]
    assert "const isArrow = wbSketchTakesCaps(parsed);" in bar[: bar.index("\n}\n")]
    # What the tool draws is stored by kind, so the lists read it back.
    assert "Object.assign(blob, wbToolCaps())" in SOURCE
    fmt = (ROOT / "frontend" / "js" / "whiteboard-format.js").read_text(encoding="utf-8")
    #: 22cc1f2 put "strokealpha" (line opacity) after "stroke" in the arrow's row; the
    #: ends ("caps") are still offered, which is what this line holds.
    assert 'arrow: ["stroke", "strokealpha", "width", "dash", "caps"' in fmt and "wbRegenerateShapeCaps(parsed.d" in fmt


def _sized(kind: str, size: str | None) -> str:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    start = SOURCE.index("const WB_CAP_KINDS")
    head_src = SOURCE[start : SOURCE.index("function wbCapPath(", start)]
    script = (
        _function("wbArrowHeadPath") + head_src + _function("wbFilledTriangle") + _function("wbCapPathMore")
        + _function("wbCapPath") + _function("wbRegenerateShapeCaps")
        + f"console.log(wbRegenerateShapeCaps('M 0 0 L 100 0', 'none', {json.dumps(kind)}, 18, {{ endSize: {json.dumps(size)} }}));"
    )
    return subprocess.run([node, "-e", script], capture_output=True, text=True, check=True).stdout.strip()


def _reach(path: str) -> float:
    """How far back from the tip (x 100) the end's ink reaches."""
    xs = [float(x) for x in re.findall(r"(-?\d+(?:\.\d+)?) -?\d+(?:\.\d+)?", path.split("L 100 0", 1)[1])]
    return 100 - min(xs)


def test_decision_e2_and_e3_ends_and_the_end_size():
    """INBOX 826, the owner: "can there be more arrow options on the links and
    lines?? can there be a custom memorymapai unique arrow design as well??"
    Decision E2 adds the stealth arrow, cross, half and double arrow (the dot
    is the filled circle) and a size per end; E3 the signature end, first in
    its own group, while a new line's default stays the open arrow."""
    paths = _paths()
    for kind in ("stealth", "cross", "half-arrow", "double-arrow", "memorymap"):
        assert paths[kind], kind
    assert paths["stealth"].count("Z") >= 4, "the stealth arrow is filled"
    assert paths["half-arrow"].count("M") == 1 and paths["double-arrow"].count("M") == 4
    assert paths["memorymap"].count("A") >= 2, "the signature end carries the mark's node dot"
    for which in ("startcap", "endcap"):
        select = INDEX[INDEX.index(f'id="wb-prop-{which}"') :]
        assert select.index('<optgroup label="Tessellate">') < select.index('<optgroup label="Plain ends">')
    assert 'window.currentArrowHead = WB_CAP_KINDS.includes(e.target.value) ? e.target.value : "arrow"' in SOURCE
    # Small, medium, large: the mark's reach scales, medium is the old length.
    small, medium, large = (_reach(_sized("arrow", s)) for s in ("s", None, "l"))
    assert small < medium < large and abs(medium - 18 * 0.866) < 0.1
    assert _reach(_sized("arrow", "m")) == medium, "medium (or unknown) is the saved look"
    for which in ("start", "end"):
        assert f'id="wb-prop-{which}size"' in INDEX and f'id="wb-fmt-{which}size"' in INDEX
    assert '"startCapSize", "endCapSize"' in SOURCE, "the style painter carries the sizes"
    caps = _function("wbLinkCaps")
    assert "startCapSize" in caps and "endCapSize" in caps
    # Every link path (straight, curved, bent, elbow, through points) passes the size.
    assert SOURCE.count("caps?.endSize") >= 6 and SOURCE.count("caps?.startSize") >= 6
    inter = (ROOT / "frontend" / "js" / "whiteboard-interchange.js").read_text(encoding="utf-8")
    assert 'cross: "cross"' in inter and 'openAsync: "half-arrow"' in inter
