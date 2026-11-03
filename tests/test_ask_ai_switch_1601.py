"""INBOX 1601: the Ask bar's AI switch looked on with no model until it was clicked.

The owner: "the use ai button is still visually enabled?? but if I click it it
visually disables". The switch redrew only when the offline notice changed;
a hidden notice, or one drawn before the lazy file loaded, never changes, so
the switch kept its neutral (enabled) look until a click redrew it.
"""

from __future__ import annotations

from pathlib import Path

JS = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "ask-compose.js").read_text(encoding="utf-8")


def _wire() -> str:
    start = JS.index("function wireAskUseAi(")
    return JS[start : JS.index("\n}\n", start)]


def test_the_switch_follows_the_status_pill_not_only_the_notice():
    wire = _wire()
    assert '$("ai-status")' in wire
    assert 'watch.observe(pill, { attributes: true, attributeFilter: ["data-level"] })' in wire


def test_a_click_while_the_model_is_off_stores_nothing():
    wire = _wire()
    change = wire[wire.index('addEventListener("change"') :]
    guard = change.index("aiIsOff()")
    assert guard < change.index("prefs.set(ASK_ANSWER_FROM_KEY")
    assert "return renderAskUseAi()" in change[:guard + 40]
