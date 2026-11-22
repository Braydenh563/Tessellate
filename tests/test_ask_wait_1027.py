"""A model server that accepts and never answers must not hold a turn (INBOX 1420).

The owner, 2026-10-27: a small notebook, no model running, and the trace's
first step at 14.30 s. A refused or silent runner was probed again by every
liveness check of a turn (five or more), each waiting its full read budget:
measured 4 to 9 s before the first step against a socket that listens and says
nothing, 0.7 s once the first silence was remembered.
"""

from __future__ import annotations

import json
import socket
import threading

import pytest

from tessellate.ai import ollama_client
from tessellate.ai.ollama_client import OllamaClient
from tessellate.ai.openai_client import OpenAICompatClient
from tessellate.core import deps
from tessellate.entry import manager

#: Counted, not timed (L-general-70): the claim is one probe, so the tests count the
#: connections that reached the silent runner; each probe's wait is its own 1 s budget.


@pytest.fixture()
def silent_server():
    """A listener that accepts and never answers; counts what reached it."""
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(50)
    held: list = []

    def accept() -> None:
        while True:
            try:
                held.append(srv.accept())
            except OSError:
                return

    threading.Thread(target=accept, daemon=True).start()
    yield f"http://127.0.0.1:{srv.getsockname()[1]}", held
    srv.close()
    for conn, _ in held:
        conn.close()


def test_repeated_liveness_checks_wait_once(silent_server):
    url, held = silent_server
    client = OllamaClient(base_url=url)
    answers = [client.is_running() for _ in range(8)]
    assert answers == [False] * 8
    assert len(held) == 1


def test_an_openai_shaped_server_is_remembered_too(silent_server):
    url, held = silent_server
    client = OpenAICompatClient(base_url=url + "/v1")
    assert [client.is_running() for _ in range(6)] == [False] * 6
    assert len(held) == 1


def test_a_server_that_wakes_is_seen_again(silent_server):
    url, _ = silent_server
    client = OllamaClient(base_url=url)
    assert client.is_running() is False
    assert ollama_client.is_quiet(url) is True
    ollama_client.forget_quiet(url)
    assert ollama_client.is_quiet(url) is False


def test_the_answer_does_not_wait_on_a_silent_runner(app_state, silent_server):
    url, held = silent_server
    from fastapi.testclient import TestClient

    from tessellate.api.app import create_app
    from tests.fakes import FakeEmbeddingService

    deps.override_ai(ollama=OllamaClient(base_url=url), embeddings=FakeEmbeddingService(available=False))
    session = deps.get_db().session()
    for i in range(12):
        manager.create_entry(session, f"# Friend {i}\n\nTalked with a friend about social connections {i}.")
    session.commit()
    client = TestClient(create_app())
    body = {"question": "give me an overview of my social connections", "use_tools": False}

    def ask() -> None:
        seen = []
        with client.stream("POST", "/chat/stream", json=body) as response:
            for line in response.iter_lines():
                if line.strip():
                    seen.append(json.loads(line)["type"])
        assert "answer" in seen

    ask(), ask()
    assert len(held) == 1  # one probe for both answers, not one each
