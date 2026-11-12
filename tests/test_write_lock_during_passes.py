"""No model call inside a write transaction (audit 2026-10-05, ARCH-01).

Measured before this: during `POST /night/run` against a fake server that
took 2.5 s a round, three `POST /entries` each failed with a 500 after
5.1 s, SQLite's busy timeout. The night pass added and flushed its
`NightRun` row (an INSERT, so its connection held the write lock) and then
called the model once per note with that lock still held; the entity pass
had the same shape. With a real local model each call is seconds to tens of
seconds, so "Run now" made every save fail for minutes.

The rule these tests hold: a background pass reads, releases, asks the
model, then writes in a short transaction of its own. A save made while the
model is thinking returns at once.
"""

from __future__ import annotations

import sqlite3
import threading
import time

from tessellate.ai import entities, facts
from tessellate.core import deps
from tests.fakes import FakeOllama

#: How long the fake model takes per call. Long enough that a save blocked
#: behind it is unmistakable, short enough to keep the file quick.
SLOW = 1.5

CLAIMS = (
    "The batch size should stay at 32. Should we move to 64? "
    "The launch is on the fourth. Who owns the rollback plan?"
)


class SlowOllama(FakeOllama):
    """A model that thinks for `SLOW` seconds, says when it starts, and
    checks, while it thinks, that nobody holds the database's write lock."""

    def __init__(self) -> None:
        super().__init__(running=True)
        self.thinking = threading.Event()
        self.lock_free: list[bool] = []

    def think(self) -> None:
        # Probe before the signal: the signal lets the test's own save start, and a probe after it
        # could catch that save's lock rather than the pass's (PR 216 CI, 3.13: [False, True]).
        self.lock_free.append(_write_lock_is_free())
        self.thinking.set()
        time.sleep(SLOW)

    def chat(self, model, messages, mode=None):  # noqa: ANN001, ANN201
        self.think()
        return {"content": "0, 1"}


def _write_lock_is_free() -> bool:
    """Can a second connection take SQLite's write lock right now, without
    waiting? The property itself, where the save's elapsed time was only a
    proxy for it: a CI runner once stalled a save that took 0.016 s here for
    1.7 s (Python 3.12, 2026-10-06), which read as "blocked behind the model"
    though nothing held the lock."""
    path = deps.get_db().engine.url.database
    probe = sqlite3.connect(path, timeout=0)
    try:
        probe.execute("BEGIN IMMEDIATE")
        probe.execute("ROLLBACK")
        return True
    except sqlite3.OperationalError:
        return False
    finally:
        probe.close()


def _save_while_thinking(client, slow: SlowOllama, worker: threading.Thread) -> tuple[int, float]:
    worker.start()
    assert slow.thinking.wait(10), "the pass never asked the model"
    started = time.monotonic()
    reply = client.post("/entries", json={"content": "Written while the model was thinking."})
    elapsed = time.monotonic() - started
    worker.join(30)
    return reply.status_code, elapsed


def test_a_save_during_a_night_pass_is_not_blocked(client, app_state):
    for _ in range(2):
        client.post("/entries", json={"content": CLAIMS})
    slow = SlowOllama()
    outcome: dict = {}

    def night() -> None:
        with deps.get_db().session() as session:
            outcome.update(facts.run(session, budget=20_000, force=True, provider=slow, model="m"))
            session.commit()

    status, elapsed = _save_while_thinking(client, slow, threading.Thread(target=night))
    assert status == 201
    assert slow.lock_free and all(slow.lock_free), f"a pass held the write lock while the model thought: {slow.lock_free}"
    # A save that queued behind the model would take the whole call and
    # more; a scheduling stall on a busy runner is the one other way past it.
    assert elapsed < 2 * SLOW, f"the save waited {elapsed:.2f}s behind the model"
    assert outcome.get("derived"), outcome
    assert outcome["run_id"]


def test_a_save_during_an_entity_pass_is_not_blocked(client, app_state):
    for index in range(2):
        client.post("/entries", json={"content": f"Sam and Priya met in Leeds about the launch plan, note {index}."})
    slow = SlowOllama()
    slow.chat = lambda model, messages, mode=None: (slow.think(), {"content": "Sam|person, Leeds|place"})[1]
    processed: list[int] = []

    def pass_() -> None:
        with deps.get_db().session() as session:
            processed.append(entities.extract_entities_pass(session, deps.get_model_manager(), slow, limit=5))

    status, elapsed = _save_while_thinking(client, slow, threading.Thread(target=pass_))
    assert status == 201
    assert slow.lock_free and all(slow.lock_free), f"a pass held the write lock while the model thought: {slow.lock_free}"
    # A save that queued behind the model would take the whole call and
    # more; a scheduling stall on a busy runner is the one other way past it.
    assert elapsed < 2 * SLOW, f"the save waited {elapsed:.2f}s behind the model"
    assert processed and processed[0] >= 2


def test_a_locked_database_is_a_503_that_says_so(client):
    """When a write does lose the race, the answer is a plain sentence and a
    status a client can retry on, not "Something went wrong"."""
    from sqlalchemy.exc import OperationalError

    from fastapi.testclient import TestClient

    from tessellate.api.app import create_app

    app = create_app()

    def _locked() -> dict:
        raise OperationalError("INSERT", {}, Exception("database is locked"))

    # Ahead of the static mount at "/", which would otherwise answer 404.
    app.add_api_route("/__locked", _locked, methods=["GET"])
    app.router.routes.insert(0, app.router.routes.pop())

    reply = TestClient(app, raise_server_exceptions=False).get("/__locked")
    assert reply.status_code == 503
    body = reply.json()
    assert body["code"] == "busy"
    assert "busy" in body["detail"]
