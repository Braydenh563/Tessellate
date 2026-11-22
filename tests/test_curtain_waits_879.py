"""L-world-class-879: the opening curtain lifted on the dashboard's widgets
alone, and in 1 of 16 boots the hero line (one row growing to four) and the
first steps (a card and a dock menu) landed after it, moving the page 0.053 in
view. The curtain now waits for all three."""

from __future__ import annotations

from tests._app_js import frontend_text


def _fn(text: str, name: str) -> str:
    start = text.index(f"function {name}(")
    return text[start : text.index("\n}\n", start)]


def test_the_hero_line_and_the_first_steps_are_held_for_the_curtain():
    js = frontend_text("dashboard.js")
    assert "window.dashHeroDrawn = Promise.allSettled([renderDashSubmessage(), renderDashGlance()]);" in js
    lazy = _fn(js, "renderFirstStepsLazy")
    assert "dashLine.steps = lazyScript(" in lazy and ".then(() => dashLine.menu);" in lazy
    assert "dashLine.menu = renderGetStarted();" in _fn(frontend_text("first-run.js"), "renderFirstSteps")
