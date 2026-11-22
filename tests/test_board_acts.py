"""The board's acts (CHAT_PLAN section 2, the whiteboard and mind map row):
"arrange as a grid of 3" through the act registry, the act set at 1.0 on the
fixture (`fixtures/composer/board_acts_1010.json`), every act with its
inverse (the board's Undo), and the palette asking the route rather than
reading the words itself."""

from __future__ import annotations

from tests._app_js import frontend_text
import json
from pathlib import Path

from tessellate.ai import acts
from tests import _js_scope

ROOT = Path(__file__).resolve().parents[1]
ROWS = json.loads((ROOT / "tests/fixtures/composer/board_acts_1010.json").read_text(encoding="utf-8"))["rows"]


def test_the_act_set_is_read_at_one():
    missed = []
    for row in ROWS:
        got = acts.board_parse(row["text"])
        said = (got["intent"], got["slots"]) if got else (None, {})
        if said != (row["intent"], row["slots"]):
            missed.append((row["text"], said))
    assert not missed, f"{len(ROWS) - len(missed)} of {len(ROWS)}: {missed}"
    assert len(ROWS) >= 40


def test_every_board_act_has_an_inverse_and_a_help_line():
    for act in acts.BOARD_ACTS:
        assert act.inverse == "undo" and act.help and act.example
        assert acts.board_parse(act.example)["intent"] == act.intent


def test_the_route_serves_the_act(client):
    token = client.post("/auth/setup", json={"password": "first-pass"}).json()["token"]
    got = client.get("/read/board", params={"q": "arrange as a grid of 3"}, headers={"X-Auth-Token": token})
    assert got.json()["act"]["slots"] == {"columns": 3}
    none = client.get("/read/board", params={"q": "show the grid"}, headers={"X-Auth-Token": token})
    assert none.json() == {"act": None}


def test_the_palette_runs_it_through_the_boards_commands():
    js = (ROOT / "frontend/js/whiteboard-commands.js").read_text(encoding="utf-8")
    assert '"/read/board' in js
    assert "wbArrangeGridSelection(" in js
    board = frontend_text("whiteboard.js")
    assert "async function wbArrangeGridSelection(columns)" in board
    palette = _js_scope.unwrapped((ROOT / "frontend/js/app-palette.js").read_text(encoding="utf-8"))
    assert "wbPaletteActRow(query)" in palette


def test_a_stickys_day_is_read_for_its_chip(client):
    token = client.post("/auth/setup", json={"password": "first-pass"}).json()["token"]
    got = client.post("/read/dates", headers={"X-Auth-Token": token}, json={
        "texts": ["Launch party friday 3pm", "Retro was on monday", "no day", 'he said "tuesday"'],
        "now": "2026-10-10T14:00:00+00:00",
    }).json()["dates"]
    assert got[0]["short"] == "Fri 16 Oct, 15:00"
    assert got[0]["reminder"] == {"text": "Launch party", "due_at": "2026-10-16T15:00+00:00"}
    assert got[1]["short"] == "Mon 5 Oct" and got[1]["reminder"] is None
    assert got[2] is None and got[3] is None


def test_the_board_paints_the_chip_from_the_route():
    board = frontend_text("whiteboard.js")
    assert '"/read/dates"' in board and "wbScheduleStickyDates();" in board
