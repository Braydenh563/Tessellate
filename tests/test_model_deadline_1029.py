"""A hung model stalls nothing (audit 1029 H3, H4).

The fake transport is a real local socket server that answers `/api/tags` and
then never answers `/api/chat`: the "chathang" mode of the audit, where the
request has no response object to close and only the socket can end it.
"""

from __future__ import annotations

import json
import socket
import threading
import time

import pytest
from fastapi.testclient import TestClient

from tessellate.ai import ollama_client, provider_http
from tessellate.core import activity, deadline, deps


class HangingModel:
    """Accepts connections; answers `/api/tags`; holds any other request open
    until the client closes it, and counts how many it saw closed."""

    def __init__(self, answer_tags: bool = True) -> None:
        self.answer_tags = answer_tags
        self.server = socket.socket()
        self.server.bind(("127.0.0.1", 0))
        self.server.listen(8)
        self.url = f"http://127.0.0.1:{self.server.getsockname()[1]}"
        self.closed_by_client = 0
        self.held = 0
        self._stop = False
        threading.Thread(target=self._accept, daemon=True).start()

    def _accept(self) -> None:
        while not self._stop:
            try:
                conn, _ = self.server.accept()
            except OSError:
                return
            threading.Thread(target=self._serve, args=(conn,), daemon=True).start()

    def _serve(self, conn: socket.socket) -> None:
        data = b""
        conn.settimeout(10)
        try:
            while b"\r\n\r\n" not in data:
                chunk = conn.recv(4096)
                if not chunk:
                    return
                data += chunk
            if self.answer_tags and data.startswith(b"GET /api/tags"):
                body = json.dumps({"models": [{"name": "m"}]}).encode()
                conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: %d\r\n\r\n" % len(body) + body)
                return
            self.held += 1
            while True:
                chunk = conn.recv(65536)  # the rest of the body, then silence
                if not chunk:
                    self.closed_by_client += 1
                    return
        except OSError:
            self.closed_by_client += 1
        finally:
            conn.close()

    def close(self) -> None:
        self._stop = True
        self.server.close()


@pytest.fixture()
def hanging():
    model = HangingModel()
    yield model
    model.close()


def _wait(check, seconds=3.0) -> bool:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if check():
            return True
        time.sleep(0.02)
    return check()


def test_stop_cuts_a_call_still_waiting_for_the_first_byte(hanging):
    event = activity.StopEvent()
    job = activity.Job("generation", "t", None, True, None, event)
    threading.Timer(0.3, event.set).start()
    started = time.monotonic()
    with activity.bind(job), pytest.raises(provider_http.RequestException):
        provider_http.post(f"{hanging.url}/api/chat", json={"x": 1}, stream=True, timeout=(3, 60))
    assert time.monotonic() - started < 2.0
    assert _wait(lambda: hanging.closed_by_client == 1)


def test_a_call_with_no_flag_is_the_plain_request_path(hanging, monkeypatch):
    seen = []
    monkeypatch.setattr(provider_http.requests, "request", lambda method, url, **kw: seen.append((method, url)) or "r")
    assert provider_http.post("http://x/y") == "r" and seen == [("POST", "http://x/y")]


def test_one_table_names_every_deadline():
    assert deadline.seconds_for("POST", "/drafts/title") is not None
    assert deadline.seconds_for("post", "/help/ask") == deadline.DEADLINES[("POST", "/help/ask")]
    assert deadline.seconds_for("POST", "/chat/stream") is None
    assert all(0 < seconds <= 60 for seconds in deadline.DEADLINES.values())


def test_a_utility_route_answers_within_its_deadline_and_cuts_the_model(app_state, hanging, monkeypatch):
    from tessellate.api.app import create_app

    monkeypatch.setitem(deadline.DEADLINES, ("POST", "/drafts/title"), 0.6)
    deps.override_ai(ollama=ollama_client.OllamaClient(base_url=hanging.url))
    api = TestClient(create_app())
    started = time.monotonic()
    response = api.post("/drafts/title", json={"draft": "A draft about the garden and the spring plan."})
    took = time.monotonic() - started
    assert response.status_code == 200 and response.json()["title"] == ""
    assert took < 4.0
    assert hanging.held >= 1 and _wait(lambda: hanging.closed_by_client >= 1)


def test_a_route_with_no_fallback_answers_504_after_its_deadline(app_state, hanging, monkeypatch):
    from tessellate.api.app import create_app
    from tessellate.api import routes_drafts
    from tessellate.ai.provider import ProviderError

    monkeypatch.setitem(deadline.DEADLINES, ("POST", "/drafts/title"), 0.5)

    def no_fallback(draft, manager, ollama):  # noqa: ANN001
        try:
            ollama.chat("m", [{"role": "user", "content": draft}])
        except ollama_client.OllamaError as exc:
            raise ProviderError(str(exc)) from exc

    monkeypatch.setattr(routes_drafts.drafter, "suggest_title", no_fallback)
    deps.override_ai(ollama=ollama_client.OllamaClient(base_url=hanging.url))
    api = TestClient(create_app(), raise_server_exceptions=False)
    response = api.post("/drafts/title", json={"draft": "A draft"})
    assert response.status_code == 504 and response.json()["code"] == "model_slow"


def test_a_stopped_chat_stream_ends_and_the_model_sees_the_close(app_state, hanging):
    event = activity.StopEvent()
    client = ollama_client.OllamaClient(base_url=hanging.url)
    seen = []

    def run() -> None:
        job = activity.Job("generation", "t", None, True, None, event)
        with activity.bind(job):
            try:
                list(client.chat_stream("m", [{"role": "user", "content": "hi"}]))
            except ollama_client.OllamaError as exc:
                seen.append(exc)

    worker = threading.Thread(target=run)
    worker.start()
    assert _wait(lambda: hanging.held == 1)
    event.set()
    worker.join(3)
    assert not worker.is_alive() and seen
    assert _wait(lambda: hanging.closed_by_client == 1)


def test_a_closed_browser_sets_the_flag(app_state, monkeypatch):
    import asyncio

    class Gone:
        scope = {"route": type("R", (), {"path": "/drafts/title"})()}
        method = "POST"
        state = type("S", (), {})()
        url = type("U", (), {"path": "/drafts/title"})()

        async def is_disconnected(self) -> bool:
            return True

    monkeypatch.setattr(deadline, "WATCH_SECONDS", 0.01)

    async def go() -> bool:
        guard = deadline.guard(Gone())
        await guard.__anext__()
        flag = deadline.current()
        await asyncio.sleep(0.1)
        fired = flag.is_set()
        await guard.aclose()
        return fired

    assert asyncio.run(go())


@pytest.fixture()
def silent():
    """The audit's `hang` mode: accepts every connection, answers none."""
    model = HangingModel(answer_tags=False)
    yield model
    model.close()


def _timed(api, path):
    started = time.monotonic()
    response = api.get(path)
    return response, time.monotonic() - started


def test_decorating_routes_do_not_wait_on_a_silent_backend(app_state, silent):
    from tessellate.api.app import create_app

    deps.override_ai(ollama=ollama_client.OllamaClient(base_url=silent.url))
    api = TestClient(create_app())
    paths = [
        "/models/hardware", "/activity", "/embedding-models/choices", "/entries/tensions",
        "/insights/greeting", "/support-bundle",
    ]
    for path in paths:  # the first pass may pay one short budget; the second is the steady state
        _timed(api, path)
    for path in paths:
        response, took = _timed(api, path)
        assert response.status_code == 200, path
        assert took < 0.3, (path, took)


def test_the_searxng_status_does_not_wait_on_a_docker_that_hangs(app_state, monkeypatch):
    from tessellate.api.app import create_app
    from tessellate.api import routes_websearch
    from tessellate.search import searxng_manager

    release = threading.Event()
    monkeypatch.setattr(searxng_manager, "docker_available", lambda: release.wait(5) and False)
    monkeypatch.setattr(routes_websearch, "STATUS_BUDGET", 0.1)
    api = TestClient(create_app())
    first, took = _timed(api, "/websearch/searxng/status")
    assert first.status_code == 503 and took < 0.5
    release.set()
    assert _wait(lambda: api.get("/websearch/searxng/status").status_code == 200)
    second, took = _timed(api, "/websearch/searxng/status")
    assert second.status_code == 200 and took < 0.3
