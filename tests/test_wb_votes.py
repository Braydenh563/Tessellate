"""Voting dots and a workshop timer (INBOX 1313, plan row 14)."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WB = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")
CMD = (ROOT / "frontend" / "js" / "whiteboard-commands.js").read_text(encoding="utf-8")
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "css" / "library-lazy.css").read_text(encoding="utf-8")
DESIGN = (ROOT / "docs" / "DESIGN.md").read_text(encoding="utf-8")


def _function(name: str) -> str:
    start = WB.index(f"function {name}(")
    return WB[start : WB.index("\n}\n", start) + 3]


def _node(names, expr: str):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    consts = "const WB_VOTE_MAX = 99;"
    code = consts + "".join(_function(n) for n in names) + f"console.log(JSON.stringify({expr}));"
    return json.loads(subprocess.run([node, "-e", code], capture_output=True, text=True, check=True).stdout)


def test_a_vote_count_steps_within_its_bounds_and_clears_at_zero() -> None:
    names = ("wbVotesAfter",)
    assert _node(names, "wbVotesAfter(undefined, 1)") == 1
    assert _node(names, "wbVotesAfter(3, 1)") == 4
    assert _node(names, "wbVotesAfter(1, -1) ?? null") is None
    assert _node(names, "wbVotesAfter(0, -1) ?? null") is None
    assert _node(names, "wbVotesAfter(99, 1)") == 99
    assert _node(names, "wbVotesAfter('x', 1)") == 1


def test_the_timer_reads_as_minutes_and_seconds_from_a_given_clock() -> None:
    names = ("wbTimerLeft", "wbTimerText")
    assert _node(names, "wbTimerText(5 * 60000)") == "5:00"
    assert _node(names, "wbTimerText(65000)") == "1:05"
    assert _node(names, "wbTimerText(999)") == "0:01"
    assert _node(names, "wbTimerText(0)") == "0:00"
    assert _node(names, "wbTimerText(-5)") == "0:00"
    assert _node(names, "wbTimerLeft(10000, 4000)") == 6000
    assert _node(names, "wbTimerLeft(10000, 12000)") == 0


def test_every_command_is_in_the_table_and_the_edit_menu() -> None:
    for command in ("vote", "unvote", "clear-votes", "timer"):
        assert f'id: "{command}"' in CMD, command
    #: The Board menu is the one with room (622px of 781; the Edit menu already scrolls), so the
    #: dot and the timer rows live there; taking one off is in Ctrl+K.
    board = HTML[HTML.index('id="wb-board-menu"') :]
    board = board[: board.index("</nav>") if "</nav>" in board else 20000]
    for command in ("vote", "clear-votes", "timer"):
        assert f'data-wb-cmd="{command}"' in board, command
    assert 'aria-label="Workshop"' in board


def test_the_dots_paint_from_the_items_own_data() -> None:
    paint = _function("wbPaintVotes")
    assert "data?.votes" in paint and "wb-votes" in paint
    assert "wbPaintVotes(this, d)" in WB
    assert ".wb-votes" in CSS


def test_an_export_draws_the_dots_too() -> None:
    assert "if (obj.data?.votes) parts.push(wbSvgVotes(obj));" in WB
    pill = _function("wbSvgVotes")
    assert "obj.data.votes" in pill and "<rect" in pill and "<text" in pill


def test_the_timer_keeps_one_timeout_and_clears_it() -> None:
    """No interval (the wake-source ratchet): one timeout aimed at the next shown second."""
    assert "clearTimeout(" in _function("wbTimerStop")
    paint = _function("wbTimerPaint")
    assert paint.count("setTimeout(") == 1 and "setInterval(" not in WB[WB.index("const wbTimer =") : WB.index("function wbOpenTimerMenu(")]
    #: It ends at zero: nothing is scheduled once the time is up.
    assert paint.index("setTimeout(") < paint.index('classList.add("wb-timer-done")')


def test_the_recipe_is_in_the_design_index() -> None:
    assert "A tally on a board item" in DESIGN and "wbPaintVotes" in DESIGN
    assert "A countdown on the board" in DESIGN and "wbTimerStart" in DESIGN
