"""The dashboard's cards are sized once when the grid is shown, not on every fill while it is hidden (INBOX 1741).

The owner's log: `frame 380ms on dashboard: style and layout`. While the widgets fill, the grid is
`.dash-filling` (`visibility: hidden`, nobody sees a span), and each card that grew woke the resize observer:
`sizeDashWidgets` ran 5 or 6 times at boot, each a forced layout of the freshly filled cards and a second
layout for the spans it wrote (85 to 217ms in all at 4x CPU, 4 runs). The settle that lifts the veil sizes once.
The 1.2s settle timer also has a name, so a frame it starts is attributed.
"""

from __future__ import annotations

from pathlib import Path

DASH = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "dashboard.js").read_text(encoding="utf-8")


def _body(head: str) -> str:
    start = DASH.index(head)
    return DASH[start : DASH.index("\n}\n", start) + 3]


def test_the_observer_does_not_size_behind_the_veil() -> None:
    body = _body("function watchDashWidgets(")
    frame = body[body.index("requestAnimationFrame(() => {") :]
    assert 'if (!grid.classList.contains("dash-filling")) sizeDashWidgets();' in frame


def test_the_settle_sizes_once_before_the_veil_lifts() -> None:
    body = _body("async function renderDashboard(")
    lift = body[body.index("settled.then(() => afterFrames(() => {") :]
    assert lift.index("sizeDashWidgets();") < lift.index('grid.classList.remove("dash-filling")')
    assert lift.index('if (window.dashSettled !== settled) return;') < lift.index("sizeDashWidgets();"), "a newer render sizes for itself"


def test_the_settle_timer_has_a_name() -> None:
    assert "setTimeout(function dashSettleTimeout() {" in _body("async function renderDashboard(")
