"""W27 (sweep-1028b): "No model connected" showed twice in the writing room. Driven offline at 1440 and 390 wide,
the room shows one notice (`#draft-offline`). This pins the markup behind that: the room holds exactly one
`.ai-offline-note` slot, so a second one cannot be added without this test saying so."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _room() -> str:
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    start = html.index('<section class="card" id="writing-room">')
    return html[start : html.index("</section>", start)]


def test_the_writing_room_has_one_offline_notice_slot() -> None:
    slots = re.findall(r'id="([^"]+)"[^>]*class="[^"]*ai-offline-note|class="[^"]*ai-offline-note[^"]*"[^>]*id="([^"]+)"', _room())
    assert [a or b for a, b in slots] == ["draft-offline"]


def test_the_room_names_no_second_model_line_in_its_markup() -> None:
    assert _room().count("No model connected") == 0
