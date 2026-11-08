"""lagjj-1108, target 1: `nameMarkBuddyTempo` read the figure's style while a send or a step was undrawn.

Probe (4x CPU, 60 notes, Atlas companion on, first chat message): the look's `getAnimations` paid 108 to
364 ms of forced style 300 ms after Send, with the idle gate already open (each stream delta dirties the
pane, and the beat after the idle callback read it before a frame drew it); `playState` paid 76 to 288 ms
a beat after a step. After: no tempo frame with forced style in three runs. Pinned by shape here.
"""

from __future__ import annotations

from pathlib import Path

AV = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "avatars.js").read_text(encoding="utf-8")


def _tempo() -> str:
    start = AV.index("function nameMarkBuddyTempo() {")
    return AV[start : AV.index("\ndocument.addEventListener(\"visibilitychange\"", start)]


def test_no_read_before_a_frame_has_drawn_the_last_beats_steps() -> None:
    tempo = _tempo()
    gate = tempo.index("if (nmbTempo.wrote && !nmbTempo.drawn")
    assert gate < tempo.index("buddy.getAnimations(") and gate < tempo.index("anim.playState)")
    assert "afterFrames(() => setTimeout(() => (nmbTempo.drawn = true), 0), 1);" in tempo
    assert "< 4" in tempo[gate : gate + 120], "bounded: three waits at most"


def test_the_periodic_look_waits_out_a_stream_and_a_written_page() -> None:
    tempo = _tempo()
    assert "typeof chatStreaming !== \"undefined\" && chatStreaming" in tempo
    assert "nmb.pageAt > nmbTempo.readyAt" in tempo
    assert "nmbTempo.readyAt = performance.now();" in tempo
    assert tempo.index("nmb.pageAt > nmbTempo.readyAt") < tempo.index("buddy.getAnimations(")
