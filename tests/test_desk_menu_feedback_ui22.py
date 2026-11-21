"""Source text: g3-size-1107 leftovers (HISTORY "From agent-remaining/companion-asks.md, Group 3"):
"a `figure_do` refusal gives no feedback, 'Sit on a window' is not greyed when none is found"
(L-ui-modernisation-22).

A refused menu request always shows on the figure, even straight after the lonely sad face, and
the menu greys "Sit on a window" when there is no window top to sit on or it is already on one."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PIL")

from tessellate.core.overlay.engine import Perch  # noqa: E402
from tests.test_desk_companion import prefs  # noqa: E402, F401
from tests.test_desk_overlay_wiring import FakeRunner, over  # noqa: E402, F401
from tests.test_overlay_parity_1683 import still  # noqa: E402

JS = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "desk-companion.js").read_text(encoding="utf-8")


def test_a_refused_request_shows_even_after_the_lonely_face() -> None:
    e, _s, t = still()
    assert e.ex.fire("refused", t)  # the lonely sad face, whose cooldown is ten seconds
    t += 3.0
    e.update(t)
    assert e.command("perch", t) is False
    assert e.ex.last[-1] == "declined" and e.ex.over[0] == "sad"


def test_the_engine_says_whether_it_can_sit_on_a_window() -> None:
    e, _s, t = still()
    assert e.perch_free() == "none"
    e.set_windows([Perch(9, 500, 400, 1300)], t)
    assert e.perch_free() == ""
    e.perch = Perch(9, 500, 400, 1300)
    assert e.perch_free() == "on"


def test_the_panel_passes_it_to_the_menu(over) -> None:  # noqa: F811
    over.set_main_hidden(True)
    FakeRunner.started[0].engine = type("E", (), {"state": "stand", "perch_free": lambda self: "none"})()
    assert over.panel_motion()["perch"] == "none"


def test_the_menu_greys_the_row_with_the_reason() -> None:
    assert 'const noPerch = { on: "Already sitting on a window", none: "No window to sit on right now" }[motion.perch];' in JS
    assert "if (motion.roam === false || stays || noPerch) {" in JS
