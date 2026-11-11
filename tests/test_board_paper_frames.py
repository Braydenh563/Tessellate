"""F2, draw.io's paper sizes (`PageSetupDialog`): the Frames set holds a page frame for each common paper size, at the
size a browser prints a CSS page at (96 dpi), so a board's frames export and present as pages."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FRAMES = json.loads((ROOT / "frontend" / "board-library" / "frames.json").read_text(encoding="utf-8"))
ITEMS = {i["key"]: i for i in FRAMES["items"]}

#: Millimetres to pixels at 96 dpi, rounded to a whole pixel.
MM = 96 / 25.4

PAPER = {
    "page-a4-portrait": (210, 297),
    "page-a4-landscape": (297, 210),
    "page-a3-landscape": (420, 297),
    "page-letter-portrait": (215.9, 279.4),
}


@pytest.mark.parametrize("key", sorted(PAPER))
def test_a_paper_frame_is_the_paper_at_96_dpi(key):
    mm_w, mm_h = PAPER[key]
    box = ITEMS[key]["payload"]["box"]
    assert abs(box["w"] - mm_w * MM) <= 1 and abs(box["h"] - mm_h * MM) <= 1


def test_the_slide_is_sixteen_by_nine():
    box = ITEMS["slide-16-9"]["payload"]["box"]
    assert box["w"] * 9 == box["h"] * 16


def test_each_paper_frame_is_one_frame_the_size_of_its_box_and_named_for_the_page():
    for key in [*PAPER, "slide-16-9"]:
        item = ITEMS[key]
        box = item["payload"]["box"]
        (frame,) = item["payload"]["items"]
        assert frame["type"] == "frame" and (frame["w"], frame["h"]) == (box["w"], box["h"])
        assert frame["data"]["content"] == item["name"] and (frame["x"], frame["y"]) == (0, 0)
        assert item["payload"]["links"] == []


def test_the_search_finds_a_page_by_its_paper_name():
    tags = {key: set(ITEMS[key]["tags"]) for key in ITEMS}
    assert {"a4", "paper"} <= tags["page-a4-portrait"] and {"a3"} <= tags["page-a3-landscape"]
    assert {"letter"} <= tags["page-letter-portrait"] and {"slide", "16:9"} <= tags["slide-16-9"]
