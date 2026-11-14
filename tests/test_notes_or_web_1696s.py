"""Notes or the web? (INBOX 1696 s): when the router reads a message as both
a question about the notebook and a lookup about the world, the answer slot
asks in one line with two chips; clear readings do not ask."""

from __future__ import annotations

import pytest

from tessellate.ai import composer_unplaced as cu
from tessellate.core import deps
from tessellate.entry import manager
from tests.test_composer_route_688 import _ask

TITLE = {"content": "# Sourdough starter\n\nFeed the starter daily."}
LOOSE = {"content": "# Baking log\n\nFed the sourdough starter at noon."}
DEFINES = {"content": "# Baking log\n\nThe sourdough starter is bubbly."}
UNRELATED = {"content": "# Dentist\n\nCheck-up booked."}


def test_a_title_match_is_clear_notes_and_does_not_ask():
    assert cu.notes_reading("sourdough starter", [TITLE]) >= 0.95
    assert not cu.torn("sourdough starter", [TITLE], web_on=True)


def test_a_lookup_with_a_looser_note_is_close_and_asks():
    assert cu.web_reading("what is a sourdough starter") >= 0.7
    assert cu.torn("what is a sourdough starter", [LOOSE], web_on=True)


def test_a_note_that_defines_it_is_clear_notes():
    assert not cu.torn("what is a sourdough starter", [DEFINES], web_on=True)


def test_no_note_or_an_unrelated_note_does_not_ask():
    assert not cu.torn("what is the capital of France", [], web_on=True)
    assert not cu.torn("what is the capital of France", [UNRELATED], web_on=True)


def test_an_explicit_web_or_notes_ask_never_asks():
    assert not cu.torn("search the web for sourdough starter", [LOOSE], web_on=True)
    assert not cu.torn("what is in my notes about the sourdough starter", [LOOSE], web_on=True)


def test_web_off_never_asks():
    assert not cu.torn("what is a sourdough starter", [LOOSE], web_on=False)


def test_the_margin_is_the_threshold():
    assert cu.CLOSE_BY == pytest.approx(0.12)
    assert cu.torn_by(0.75, 0.7) and cu.torn_by(0.7, 0.8)
    assert not cu.torn_by(1.0, 0.7) and not cu.torn_by(0.4, 0.7) and not cu.torn_by(0.6, 0.0)


@pytest.fixture()
def notebook(session):
    manager.create_entry(session, "# Baking log\n\nFed the sourdough starter at noon.")
    manager.create_entry(session, "# Dentist\n\nCheck-up booked.")
    session.commit()
    return session


def _chips(out):
    return [a for e in out.get("offer", []) if e["offer"].get("kind") == "ask" for a in e["offer"]["asks"]]


def test_the_stream_asks_with_two_chips_when_web_is_on(client, notebook):
    deps.get_config().set_preference("web_search_enabled", True)
    out = _ask(client, "what is a sourdough starter")
    assert out["text"].strip() == "Did you mean your notes or the web?"
    assert _chips(out) == ["Search my notes for sourdough starter", "Search the web for sourdough starter"]


def test_the_stream_does_not_ask_with_web_off(client, notebook):
    deps.get_config().set_preference("web_search_enabled", False)
    out = _ask(client, "what is a sourdough starter")
    assert "Did you mean your notes or the web?" not in out["text"]
    assert not any("Search the web" in c for c in _chips(out))


def test_each_chip_text_routes_to_its_side():
    for said in ("Search my notes for sourdough starter", "Search the web for sourdough starter"):
        assert not cu.torn(said, [LOOSE], web_on=True), said


def test_a_chip_sends_its_own_text_as_the_next_message():
    """The strip is the existing follow-up recipe: a press sends exactly the chip's text."""
    from tests._app_js import app_js_text

    js = app_js_text()
    strip = js[js.index("function buildFollowupStrip"):]
    strip = strip[: strip.index("\n}\n")]
    assert "chip(pick, \"\", () => sendChatMessage(pick," in strip
