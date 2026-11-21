"""A tour step that waits on a tab shows as a wait (L-general-14).

Measured with `scratchpad/ui-sweeps/toursteps.js` at 1440: Next on the chat
section's last card loads the Graph tab (2.8 s), and for all of it the card
kept "Your conversations", 4 of 4, and its ring over a list that was by then
0x0 (six faults in the sweep). Now, past a 200 ms beat, the ring clears and
Next carries the spinner recipe until the next step settles.
"""

from __future__ import annotations

from pathlib import Path
from tests import _js_scope

ROOT = Path(__file__).resolve().parent.parent
TOUR = _js_scope.unwrapped((ROOT / "frontend" / "js" / "tour.js").read_text(encoding="utf-8"))


def _body(name: str) -> str:
    start = TOUR.index(f"function {name}(")
    return TOUR[start : TOUR.index("\n}\n", start)]


def test_a_walk_marks_the_card_busy_and_clears_it_only_through_one_helper() -> None:
    assert 'setAttribute("aria-busy"' in _body("tourBusy")
    assert TOUR.count('removeAttribute("aria-busy")') == 1
    assert "tourBusy(run, true);" in _body("tourShow")


def test_past_the_beat_the_stale_ring_goes_and_next_shows_the_spinner() -> None:
    busy = _body("tourBusy")
    assert "TOUR_BUSY_BEAT_MS" in busy
    assert "run.el = null;" in busy
    assert "tourClearSpotlight();" in busy
    assert 'setBusy(next, true, "Opening…")' in busy
    assert "setBusy(next, false)" in busy
    assert "clearTimeout(run.busyTimer)" in busy


def test_closing_the_tour_never_leaves_next_busy() -> None:
    assert "tourBusy(run, false);" in _body("tourClose")


def test_the_sweep_measures_a_step_only_once_it_settles() -> None:
    sweep = (ROOT / "scratchpad" / "ui-sweeps" / "toursteps.js").read_text(encoding="utf-8")
    assert 'getAttribute("aria-busy") === "true"' in sweep


def test_toasts_step_aside_for_the_lit_control_not_only_for_focus() -> None:
    """toursteps at 1440: `#toast-box` was what was drawn at the centre of
    Chat's mode switch and gear on their steps, because focus sits on the
    card's Next and `toastYield` only measured the focused element."""
    status = (ROOT / "frontend" / "js" / "status.js").read_text(encoding="utf-8")
    start = status.index("function toastYield(")
    body = status[start : status.index("\n}\n", start)]
    assert '$("tour-spot")' in body and "meets(b, lit)" in body
    shown = _body("tourShow")
    assert shown.index('getElementById("tour-next").focus();') < shown.index("toastYield();")
    assert "toastYield();" in _body("tourClose")
