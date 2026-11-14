"""Row 70: the frame's `place` survives the real round trip (the frame event, the page's history, the
next /chat/stream) and "what did I do there" binds to it. No model, clock fixed at Sat 31 Oct 2026."""

from __future__ import annotations

from tessellate.api.chat_request import ChatTurn
from tests import _seed_1031c as seed


def test_the_place_of_an_answer_comes_back_and_binds_there(client, session, monkeypatch):
    seed.seed(session)
    go = seed.asker(client, monkeypatch)
    text, events = go("tell me about the Lisbon trip")
    frame = next((e["frame"] for e in events if e.get("type") == "frame"), None)
    assert frame and frame.get("place") == "Lisbon", frame
    turn = {"question": "tell me about the Lisbon trip", "answer": text, "frame": frame}
    assert ChatTurn(**turn).model_dump(exclude_none=True)["frame"]["place"] == "Lisbon"
    there, _ = go("what did I do there", history=[turn])
    without, _ = go("what did I do there", history=[{**turn, "frame": {**frame, "place": ""}}])
    assert "lisbon" in there.lower() and there != without, (there, without)
