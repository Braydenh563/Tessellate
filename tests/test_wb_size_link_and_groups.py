"""The W/H link and grouped multi-part elements (INBOX 1307, 1308)."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
FORMAT = (ROOT / "frontend" / "js" / "whiteboard-format.js").read_text(encoding="utf-8")


def test_link_button_sits_between_w_and_h_and_is_a_toggle() -> None:
    tag = re.search(r'<button[^>]*id="wb-fmt-link"[^>]*>', INDEX).group(0)
    assert 'aria-pressed="false"' in tag and "aria-label=" in tag
    assert INDEX.index('id="wb-fmt-w"') < INDEX.index('id="wb-fmt-link"') < INDEX.index('id="wb-fmt-h"')


def test_link_scales_the_other_side_by_the_ratio_at_link_time() -> None:
    assert "wbFmtLinkRatio" in FORMAT and "wbFmtToggleLink" in FORMAT
    assert re.search(r'on\("wb-fmt-link", "click", wbFmtToggleLink\)', FORMAT)
    assert "target / ratio" in FORMAT and "target * ratio" in FORMAT


def test_a_placed_multi_part_element_is_one_group(ai_client) -> None:
    board = ai_client.post("/whiteboard/boards", json={"name": "Groups", "type": "board"}).json()
    placed = ai_client.post(f"/whiteboard/boards/{board['id']}/place", json={"builtin": "uml/class", "x": 0, "y": 0}).json()
    ids = {s["group_id"] for s in placed["sketches"]}
    assert len(placed["sketches"]) == 4 and len(ids) == 1 and None not in ids
    single = ai_client.post(f"/whiteboard/boards/{board['id']}/place", json={"builtin": "flowchart/decision", "x": 0, "y": 0}).json()
    assert single["sketches"][0]["group_id"] is None
