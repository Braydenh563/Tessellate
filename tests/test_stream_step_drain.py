"""A chat stream's step still in its thread when the client goes is stopped and
waited for before the engine is disposed (L-world-class-892).

CI leg 1 on 586b5282 segfaulted a worker: the step queried SQLite
(`relation_types.kinds`) after an earlier test's stream was dropped, while the
next test's reset disposed the engine. A quit and a backup restore close the
database the same way.
"""

from __future__ import annotations

import asyncio
import threading

from tessellate.api.chat_agent import stop_when_gone
from tessellate.core import activity, deps, stream_steps


def test_the_engine_is_not_disposed_under_a_running_stream_step(app_state, monkeypatch):
    order: list[str] = []
    entered = threading.Event()
    stop = activity.StopEvent()

    def lines():
        entered.set()
        # Stands in for the agent's query: it runs until the stream's stop.
        stop.wait(5)
        order.append("step returned")
        yield "late line"

    engine = deps.get_db().engine
    real_dispose = engine.dispose

    def dispose(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        order.append("engine disposed")
        return real_dispose(*args, **kwargs)

    monkeypatch.setattr(engine, "dispose", dispose)

    async def go() -> None:
        agen = stop_when_gone(stop, lines())
        task = asyncio.ensure_future(agen.__anext__())
        await asyncio.to_thread(entered.wait, 2)
        # The client goes: the generator is cancelled, its step runs on.
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        await asyncio.to_thread(deps.reset_app_state)

    asyncio.run(go())
    assert order == ["step returned", "engine disposed"]
    assert stream_steps.in_flight() == 0
