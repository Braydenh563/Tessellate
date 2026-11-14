"""L270: a board exports as a PDF file written in the app, with real pages.

The browser's print window left page size and count to the print dialog. The
writer (`wbPdf.plan` and `wbPdf.build`, whiteboard-interchange.js) is plain
functions, so node runs them here and Python parses the bytes back: the page
count, the page boxes, and that every xref offset lands on its object.
"""

from __future__ import annotations

from tests._app_js import frontend_text
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
INTERCHANGE = (ROOT / "frontend" / "js" / "whiteboard-interchange.js").read_text(encoding="utf-8")
WB = frontend_text("whiteboard.js")
WRITER = INTERCHANGE[INTERCHANGE.index("const wbPdf = ") :]

#: Two frames side by side on a board 1000 x 400.
BOUNDS = {"x": 0, "y": 0, "w": 1000, "h": 400}
FRAMES = [
    {"x": 560, "y": 60, "width": 400, "height": 300},
    {"x": 40, "y": 60, "width": 400, "height": 300},
]


def _node(expr: str):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    code = WRITER + f"\nconsole.log(JSON.stringify({expr}));"
    return json.loads(subprocess.run([node, "-e", code], capture_output=True, text=True, check=True).stdout)


def _pdf(options: dict) -> bytes:
    expr = (
        "(() => { const plan = wbPdf.plan(" + json.dumps({"bounds": BOUNDS, "frames": FRAMES, **options}) + ");"
        "const jpeg = new Uint8Array([255, 216, 255, 217]);"
        "const bytes = wbPdf.build(plan.map((p) => ({ ...p, image: { jpeg, w: 10, h: 10 } })));"
        "return Array.from(bytes); })()"
    )
    return bytes(_node(expr))


def _pages(pdf: bytes) -> int:
    text = pdf.decode("latin-1")
    count = int(re.search(r"/Type /Pages /Kids \[[^\]]*\] /Count (\d+)", text).group(1))
    assert count == len(re.findall(r"/Type /Page /Parent", text)), "the tree's count is the pages in the file"
    return count


def test_a_two_frame_board_is_a_two_page_pdf():
    pdf = _pdf({"layout": "frames"})
    assert pdf.startswith(b"%PDF-1.4") and pdf.rstrip().endswith(b"%%EOF")
    assert _pages(pdf) == 2


def test_frames_come_in_reading_order():
    plan = _node("wbPdf.plan(" + json.dumps({"bounds": BOUNDS, "frames": FRAMES, "layout": "frames"}) + ")")
    assert [round(p["crop"]["x"]) for p in plan] == [28, 548], "the left frame first"


def test_one_page_fits_the_whole_board():
    assert _pages(_pdf({"layout": "fit"})) == 1


def test_a_board_with_no_frames_falls_back_to_one_page():
    plan = _node("wbPdf.plan(" + json.dumps({"bounds": BOUNDS, "frames": [], "layout": "frames"}) + ")")
    assert len(plan) == 1


def test_page_size_and_direction():
    a4 = _pdf({"size": "a4", "orientation": "portrait"}).decode("latin-1")
    assert "/MediaBox [0 0 595.28 841.89]" in a4
    letter = _pdf({"size": "letter", "orientation": "landscape"}).decode("latin-1")
    assert "/MediaBox [0 0 792 612]" in letter
    auto = _pdf({"size": "a4", "orientation": "auto"}).decode("latin-1")
    assert "/MediaBox [0 0 841.89 595.28]" in auto, "a wide board is landscape on auto"


def test_tiles_cover_the_board_and_stay_on_the_page():
    plan = _node("wbPdf.plan(" + json.dumps({"bounds": {"x": 0, "y": 0, "w": 2000, "h": 1500}, "layout": "tiles", "orientation": "portrait"}) + ")")
    assert len(plan) > 1
    area = sum(p["crop"]["w"] * p["crop"]["h"] for p in plan)
    assert abs(area - 2000 * 1500) < 1, "the tiles cover the board once"
    for p in plan:
        assert p["place"]["x"] + p["place"]["w"] <= p["page"][0] + 0.01
        assert p["place"]["y"] + p["place"]["h"] <= p["page"][1] + 0.01


def test_every_xref_offset_lands_on_its_object():
    pdf = _pdf({"layout": "frames"})
    text = pdf.decode("latin-1")
    start = int(re.search(r"startxref\n(\d+)", text).group(1))
    assert pdf[start : start + 4] == b"xref"
    rows = re.findall(r"(\d{10}) 00000 n ", text)
    assert len(rows) == 2 + 3 * 2
    for number, offset in enumerate(rows, start=1):
        assert pdf[int(offset) :].startswith(f"{number} 0 obj".encode()), number


def test_the_export_uses_the_writer_not_the_print_window():
    body = WB[WB.index("async function wbExportPdf(") :][:600]
    assert "wbPdf.build(" in body and "window.open" not in body and ".print()" not in body


def test_the_dialog_names_a_branch_when_opened_for_one():
    body = WB[WB.index("function wbExportBoard(") :][:16000]
    assert 'function wbExportBoard({ branch = false } = {})' in WB
    assert '"Export this branch" : "Export this board"' in body
    assert "dialogHead(heading, close)" in body and 'setAttribute("aria-label", heading)' in body


def test_the_maps_branch_export_opens_the_dialog_for_a_branch():
    """L267: the map's "Export this branch" opened the board's dialog titled "Export this board"."""

    js = frontend_text("whiteboard-map.js")
    body = js[js.index("function wbMapExportBranch("):][:700]
    assert "wbExportBoard({ branch: true })" in body
