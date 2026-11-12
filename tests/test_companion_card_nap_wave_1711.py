"""INBOX 1711 leftovers, in-app side: the wave at the pointer is the idle trigger alone, and the card nap needs a visible card
edge under the companion. Read as text (no browser here); the measured run is in the agent's remaining list."""

from __future__ import annotations

from pathlib import Path

JS = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "avatars.js").read_text(encoding="utf-8")


def test_the_wave_is_the_idle_trigger_alone_not_a_weighted_pick() -> None:
    assert 'act === "wavepointer" ||' in JS
    assert "w = 0;" in JS.split('act === "wavepointer" ||')[1][:120]
    assert JS.count("nmb.waveRest(x, y)") == 1 and JS.count('nameMarkBuddyAct("wavepointer"') == 1
    body = JS.split("nmb.waveRest = (x, y) => {")[1].split("\n};\n")[0]
    assert "nameMarkBuddyStill()" in body and "document.hidden" in body and "NMB_WAVE_GAP" in body


def test_the_card_nap_weighs_zero_without_a_visible_card_edge() -> None:
    assert 'act === "cardnap" && !nmb.cardEdge()' in JS
    body = JS.split("nmb.cardEdge = () => {")[1].split("\n};\n")[0]
    for need in ('nmb.perch === "card"', 'nmb.pose === "sit"', "getBoundingClientRect()", "innerHeight"):
        assert need in body
