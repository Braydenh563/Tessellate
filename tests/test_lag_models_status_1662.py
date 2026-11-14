"""INBOX 1662 (the owner's Windows log): `/models/status` 3287 ms at start-up.

Every poll asked the OCR reader question itself: `shutil.which`, a Windows folder probe and
three `find_spec` disk looks, twice (`local_available` and `engine_name`). The answer changes
only when something is installed, so a poll serves the last one and a pool thread refreshes it.
"""

from __future__ import annotations

from tests._app_js import frontend_text
import time

from tessellate.api import routes_models
from tessellate.core import ocr


def test_a_poll_serves_the_remembered_reader_and_does_not_ask_again(client, monkeypatch):
    calls = {"n": 0}

    def engine(choice=""):
        calls["n"] += 1
        return "tesseract"

    monkeypatch.setattr(ocr, "engine", engine)
    routes_models.forget_ocr_probe()
    first = client.get("/models/status").json()
    after_first = calls["n"]
    for _ in range(4):
        again = client.get("/models/status").json()
    assert calls["n"] == after_first, "four more polls asked the reader question again"
    assert first["tesseract_available"] is again["tesseract_available"] is True
    assert first["ocr_engine"] == again["ocr_engine"] == "Tesseract"


def test_a_stale_answer_is_served_and_refreshed_after(client, monkeypatch):
    answers = ["tesseract"]
    monkeypatch.setattr(ocr, "engine", lambda choice="": answers[0])
    routes_models.forget_ocr_probe()
    assert client.get("/models/status").json()["tesseract_available"] is True
    answers[0] = ""
    routes_models._ocr_probe_state["at"] -= routes_models.OCR_PROBE_TTL + 1
    stale = client.get("/models/status").json()
    assert stale["tesseract_available"] is True, "the poll waited for the refresh instead of serving the last answer"
    for _ in range(50):
        if routes_models._ocr_probe_state["value"][0] is False:
            break
        time.sleep(0.05)
    assert client.get("/models/status").json()["tesseract_available"] is False


def _body(source: str, head: str) -> str:
    start = source.index(head)
    return source[start : source.index("\n}\n", start) + 2]


def test_the_finder_arrow_reads_the_row_before_it_writes_the_class():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    move = _body((root / "frontend" / "js" / "search.js").read_text(encoding="utf-8"), "function finderMove(")
    assert move.index("row.offsetTop") < move.index('classList.add("is-active")'), "the box read must come first"
    assert move.index("box.clientHeight") < move.index('classList.remove("is-active")')


def test_the_board_chord_guard_reads_the_markup_not_the_layout():

    owns = _body(frontend_text("whiteboard.js"), "function wbOwnsChord(")
    for forbidden in ("offsetParent", "isContentEditable", "getClientRects", "getBoundingClientRect"):
        assert forbidden not in owns, forbidden


def test_the_mermaid_draw_gives_the_loop_a_turn_between_its_steps():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    draw = _body((root / "frontend" / "js" / "mermaid-frame.js").read_text(encoding="utf-8"), "async function mermaidFrameDraw(")
    assert draw.count("await mermaidFrameYield()") >= 2
    assert draw.index("await mermaidFrameYield()") < draw.index("mermaid.parse(") < draw.index("mermaid.render(")
