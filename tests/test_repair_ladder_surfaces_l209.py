"""CHAT_PLAN decision 49 (L-chat-209): the repair ladder is one contract and
each of the five surfaces takes its steps. The server owns the lines
(`reading.repair`); chat's model-stopped note is that line, the Ask box
shares chat's route, quick add asks the reading's one question, search and
the palette name the closest thing on a miss."""

from __future__ import annotations

from pathlib import Path

from tessellate.ai import reading
from tessellate.api import chat_said

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"


def _js(name: str) -> str:
    return (JS / name).read_text(encoding="utf-8")


def test_chat_and_the_ladder_say_the_model_stopped_in_one_line():
    stopped = reading.repair(None, error="timeout", composed="Your boiler note says 1.2 bar.")
    assert stopped.step == "error" and stopped.keep and stopped.line == chat_said.MODEL_STOPPED_NOTE


def test_quick_add_asks_the_readings_one_question():
    source = _js("quickadd.js")
    assert "state.reading.question" in source and "never a guess" in source


def test_search_and_the_palette_offer_the_closest_thing_on_a_miss():
    assert "finderFeatureOffer" in _js("search.js") and "finderRenderNothing" in _js("search.js")
    assert "paletteNearest" in _js("app-palette.js")


def test_no_match_names_the_closest_and_the_capability_line():
    step = reading.repair(reading.read("asdfgh", now=__import__("datetime").datetime(2026, 11, 14, 10)), closest="the Harbor note")
    assert step.step == "no_match" and step.line.startswith("The closest I have is the Harbor note.")
