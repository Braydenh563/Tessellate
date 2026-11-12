"""Graph hover decision (GRAPH_PLAN, audit Rank 36): the hover card's refill was
~17 ms of a ~50 ms hover at 500 notes and 4x CPU. A pointer's card now fills
only once the pointer rests on a note; the dot's highlight stays instant and the
keyboard's card is not delayed."""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from tests._js_scope import unwrapped

ROOT = Path(__file__).resolve().parent.parent
CANVAS = unwrapped((ROOT / "frontend" / "js" / "graph-canvas.js").read_text(encoding="utf-8"))


def _function(name: str) -> str:
    start = re.search(rf"\nfunction {name}\(", CANVAS).start() + 1
    return CANVAS[start : CANVAS.index("\n}\n", start) + 2]


def _run(script: str) -> object:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    run = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stderr
    return json.loads(run.stdout)


GATE = (
    "const GC_CARD_REST_MS = 120; let asked = [];\n"
    "const setTimeout = (fn, ms) => { asked.push(ms); return asked.length; };\n"
    "const gcRequestDraw = () => {};\n" + _function("gcCardRested")
)


def test_a_pointer_card_waits_for_the_rest_and_asks_for_one_redraw() -> None:
    out = _run(GATE + """
const s = {}; const r = [];
r.push(gcCardRested(s, 7, true, 1000));
r.push(gcCardRested(s, 7, true, 1050));
r.push(gcCardRested(s, 7, true, 1119));
r.push(gcCardRested(s, 7, true, 1120));
console.log(JSON.stringify({ r, asked }));
""")
    assert out["r"] == [False, False, False, True]
    assert out["asked"] == [121]  # one timer for the whole wait, not one per frame


def test_moving_to_another_note_restarts_the_rest_and_never_reuses_the_old_one() -> None:
    out = _run(GATE + """
const s = {}; const r = [];
gcCardRested(s, 7, true, 1000);
r.push(gcCardRested(s, 8, true, 1110));   // 7 would have been due at 1120; 8 has only just arrived
r.push(gcCardRested(s, 8, true, 1229));
r.push(gcCardRested(s, 8, true, 1230));
console.log(JSON.stringify({ r }));
""")
    assert out["r"] == [False, False, True]


def test_the_keyboard_card_is_never_delayed() -> None:
    assert _run(GATE + "console.log(JSON.stringify(gcCardRested({}, 3, false, 5)));") is True


def test_the_frame_hides_the_card_while_waiting_and_the_highlight_is_not_gated() -> None:
    frame = _function("gcHoverCardFrame")
    gate = frame.index("gcCardRested(")
    assert gate < frame.index("gcHoverCardFill(card, node, s)")
    # hidden and unlabelled while waiting: no stale card for the last note
    assert "card.hidden = true" in frame[gate : frame.index("gcHoverCardFill(")]
    assert "s._restId = null" in frame  # leaving the note resets the rest
    # the highlight (hoveredId, the grow ease) is set in the pointer handler, ungated
    handler = CANVAS[CANVAS.index("gcSetHovered(s, id);") - 200 :][:400]
    assert "gcHoverChanged(id, s)" in handler and "gcCardRested" not in handler
