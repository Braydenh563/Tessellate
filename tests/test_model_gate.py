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
    released = threading.Event()

    def chat() -> None:
        with model_gate.interactive():
            time.sleep(0.4)
        released.set()

    thread = threading.Thread(target=chat)
    thread.start()
    time.sleep(0.05)
    started = time.monotonic()
    assert model_gate.yield_to_interactive(timeout=5)
    waited = time.monotonic() - started
    thread.join()
    assert released.is_set() and waited >= 0.2


def test_background_gives_up_waiting_rather_than_starving():
    with model_gate.interactive():
        started = time.monotonic()
        assert model_gate.yield_to_interactive(timeout=0.2) is False
        assert time.monotonic() - started < 2


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
