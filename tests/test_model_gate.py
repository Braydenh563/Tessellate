"""Interactive model calls go first (audit 2026-10-05, ARCH-09, ARCH-16).

A local runner serves one request at a time, and background work (captions,
vision reading, filing jobs, the night and entity passes) started its next
call whenever it was ready, so a chat turn asked during an import waited
behind as many calls as reached the runner first. Background work now
yields between its calls while a chat turn is streaming; the next-question
suggestions are not asked for while the person is already asking again.
"""

from __future__ import annotations

import threading
import time

from tessellate.core import jobs, model_gate


def test_background_waits_for_an_interactive_call_and_then_goes():
    """Held by events, not timed (L-general-70): the yield is still waiting while
    the chat holds the gate, and goes once it lets go."""
    inside, release, yielded = threading.Event(), threading.Event(), threading.Event()

    def chat() -> None:
        with model_gate.interactive():
            inside.set()
            release.wait(5)

    thread = threading.Thread(target=chat)
    thread.start()
    assert inside.wait(5)
    results: list[bool] = []
    background = threading.Thread(target=lambda: (results.append(model_gate.yield_to_interactive(timeout=5)), yielded.set()))
    background.start()
    try:
        assert not yielded.wait(0.2), "the background call went while the chat held the gate"
    finally:
        release.set()
    thread.join(5)
    background.join(5)
    assert yielded.is_set() and results == [True]


def test_background_gives_up_waiting_rather_than_starving(monkeypatch):
    """The give-up is the timeout the gate asks for, under the 2 s budget (L-general-70)."""
    asked: list[float] = []
    real = model_gate._condition.wait_for

    def wait_for(predicate, timeout=None):
        asked.append(timeout)
        return real(predicate, timeout=timeout)

    monkeypatch.setattr(model_gate._condition, "wait_for", wait_for)
    with model_gate.interactive():
        assert model_gate.yield_to_interactive(timeout=0.2) is False
    assert asked and sum(asked) < 2


def test_a_model_lane_job_waits_for_the_chat_turn():
    pool = jobs.Pool(widths={"model": 1}, kind_lanes={"caption": "model"})
    ran_at: list[float] = []
    try:
        with model_gate.interactive():
            pool.enqueue("caption", lambda: ran_at.append(time.monotonic()))
            time.sleep(0.4)
            assert ran_at == [], "a caption ran while a chat turn was streaming"
            left = time.monotonic()
        for _ in range(50):
            if ran_at:
                break
            time.sleep(0.05)
        assert ran_at and ran_at[0] >= left
    finally:
        pool.shutdown(deadline=2.0)


def test_followups_are_not_asked_for_while_a_turn_streams(client):
    with model_gate.interactive():
        reply = client.post("/chat/followups", json={"question": "q", "answer": "a"})
    assert reply.status_code == 200
    assert reply.json() == []
