"""L-world-class-22 clause A: the dashboard says where you are when it is not the default space."""

from __future__ import annotations

from tests._app_js import JS_DIR


def app_js_text() -> str:
    return (JS_DIR / "dashboard.js").read_text(encoding="utf-8")


def test_the_space_line_is_one_sub_bit_that_opens_the_last_edited_note():
    js = app_js_text()
    assert "function dashSpaceBit(" in js
    assert 'bits.unshift(["space"' in js
    body = js[js.index("function dashSpaceBit("):]
    body = body[: body.index("\n}\n")]
    assert "flashEntry(" in body
    assert "relativeTime(" in body
    assert 'className = "dash-space-open"' in body


def test_the_line_is_for_a_named_space_other_than_the_default_or_all():
    js = app_js_text()
    start = js.index("function dashSpaceFact(")
    body = js[start : js.index("\n}\n", start)]
    assert '"default"' in body and "SPACE_ALL" in body


def test_the_guide_says_the_dashboard_names_the_space():
    from tessellate.ai.help_topics_core import HELP_TOPICS

    spaces = next(t for t in HELP_TOPICS if t["id"] == "spaces")
    assert "dashboard" in spaces["body"].lower()
