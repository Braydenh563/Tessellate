"""L130 (P7): a model server that accepts and never answers costs the first question at most the probe's own bounds
(connect 1 s plus read 1 s), then nothing for the quiet window; measured on a real silent socket, not a fake clock."""

import socket
import threading
import time

from tessellate.ai import ollama_client
from tessellate.ai.ollama_client import OllamaClient


def test_a_silent_server_is_probed_once_within_two_and_a_half_seconds():
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(5)
    held = []
    threading.Thread(target=lambda: held.append(server.accept()), daemon=True).start()
    base = f"http://127.0.0.1:{server.getsockname()[1]}"
    ollama_client._down_until.clear()
    try:
        runner = OllamaClient(base)
        start = time.monotonic()
        assert runner.is_running() is False
        first = time.monotonic() - start
        start = time.monotonic()
        assert runner.is_running() is False
        second = time.monotonic() - start
    finally:
        server.close()
        ollama_client._down_until.clear()
    assert first < 2.5, first
    assert second < 0.05, second
    assert ollama_client.CONNECT_TIMEOUT_SECONDS + ollama_client.PROBE_READ_SECONDS <= 2.0
