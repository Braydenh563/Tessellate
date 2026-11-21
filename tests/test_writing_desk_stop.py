"""The writing desk's Stop mid-pass and its thinking stream, on a real socket (L-world-class-65).

The stand-in server (`scratchpad/fake_openai_server.py`) answers in 150 ms, too fast to press
Stop in; with `STREAM_DELAY_MS` it is slow enough, and `THINK` makes it send `reasoning_content`
pieces first, as a reasoning model's server does. Real inference is still unverified (CLAUDE.md 4).
"""

from __future__ import annotations

import importlib.util
import json
import threading
import time
from pathlib import Path

import pytest

from tessellate.ai import drafter
from tessellate.ai.openai_client import OpenAICompatClient
from tessellate.core import activity

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _scratch_data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("TESSELLATE_DATA_DIR", str(tmp_path))


@pytest.fixture()
def server(monkeypatch):
    spec = importlib.util.spec_from_file_location("fake_openai_server_desk", ROOT / "scratchpad" / "fake_openai_server.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    httpd = module.serve(0)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    monkeypatch.setattr(module, "STREAM_DELAY_MS", 300)
    client = OpenAICompatClient(f"http://127.0.0.1:{httpd.server_address[1]}/v1", timeout=10)
    yield module, client
    httpd.shutdown()
    httpd.server_close()


class _Manager:
    def chat_model(self) -> str:
        return "fake-local-tools"


def _pass(client):
    return drafter.compose_stream("bread notes", "", _Manager(), client)


def test_a_stopped_pass_ends_with_the_stopped_line_and_stops_reading(server):
    module, client = server
    lines = activity.tracked_stream("generation", "Drafting", (json.dumps(e) + "\n" for e in _pass(client)), stopped_line=activity.STOPPED_DONE)
    seen = []
    stopped_at = None
    for line in lines:
        seen.append(json.loads(line))
        if stopped_at is None and seen[-1]["type"] == "delta":
            activity.stop(activity.snapshot()[0]["id"])
            stopped_at = time.monotonic()
    settled = time.monotonic() - stopped_at
    # Seven pieces at 300 ms (2.1 s) were still to come: a stop that read them out is not one.
    assert settled < 1.2, settled
    assert seen[-1] == {"type": "done", "stopped": True}
    assert sum(e["type"] == "delta" for e in seen) == 1
    assert all("draft" not in e for e in seen)  # no finished draft was ever sent, so none can be kept
    # The model request was closed: the server's next writes find nobody there, and it stops short of all eight.
    deadline = time.monotonic() + 3
    while not module.STREAM_LOG["gone"] and time.monotonic() < deadline:
        time.sleep(0.05)
    assert module.STREAM_LOG["gone"] is True
    assert module.STREAM_LOG["pieces"] < 8
    assert activity.snapshot() == []


def test_the_thinking_arrives_first_and_apart_from_the_draft(server):
    module, client = server
    module.THINK = "Bread: the user wants proving times."
    module.STREAM_DELAY_MS = 0
    events = list(_pass(client))
    kinds = [e["type"] for e in events]
    assert kinds.index("thinking") < kinds.index("delta") and kinds[-1] == "done"
    thought = "".join(e["text"] for e in events if e["type"] == "thinking")
    draft = "".join(e["text"] for e in events if e["type"] == "delta")
    assert thought == module.THINK
    assert module.THINK not in draft
    assert events[-1]["draft"] == draft.strip() and events[-1]["thinking"] == thought


def test_the_client_keeps_the_pass_clean_when_stopped_while_only_thinking(server):
    module, client = server
    module.THINK = "x" * 30
    stream = _pass(client)
    first = next(stream)
    assert first["type"] == "thinking"
    stream.close()
    time.sleep(1.2)
    assert module.STREAM_LOG["pieces"] == 0  # no answer text had been written when it was stopped
