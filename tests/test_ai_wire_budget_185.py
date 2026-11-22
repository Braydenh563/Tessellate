"""What every common AI interaction sends a model, ratcheted (L-world-class-185).

Driven against the stand-in OpenAI server on a real socket
(`scratchpad/fake_openai_server.py`); real inference is unverified (CLAUDE.md 4).
Measured 2026-11-22: a note save makes one filing call of about 640 bytes; a
tool turn makes two calls of at most 8,743 bytes offering at most 16 tools; a
greeting or a date question makes one call with no tools, about 1,300 bytes.
The caps sit just over those figures: a rise is a prompt or tool list that grew
and is to be measured and justified, never a cap to widen.
"""

from __future__ import annotations

import importlib.util
import io
import json
import threading
import time
from datetime import datetime
from pathlib import Path

import pytest

from tests._clock import pin_clock

ROOT = Path(__file__).resolve().parents[1]

#: (question, model calls, largest request in bytes, most tools offered)
TURNS = [
    ("search my notes and list my tags", 2, 9_000, 16),
    ("what do I know about bread", 2, 8_000, 12),
    ("hi", 1, 1_500, 0),
    ("what is due this week", 1, 1_500, 0),
]
SAVE_CALLS, SAVE_BYTES = 1, 800


@pytest.fixture(autouse=True)
def _scratch_data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("TESSELLATE_DATA_DIR", str(tmp_path))
    pin_clock(monkeypatch, datetime(2026, 11, 18, 10, 0))  # a Wednesday: "this week" has days either side


@pytest.fixture()
def wire(ai_client):
    from tessellate.ai.openai_client import OpenAICompatClient
    from tessellate.core import deps

    spec = importlib.util.spec_from_file_location("fake_openai_server_wire", ROOT / "scratchpad" / "fake_openai_server.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    seen: list[dict] = []
    answer = module.Handler.do_POST

    def recorded(handler) -> None:  # noqa: ANN001
        raw = handler.rfile.read(int(handler.headers.get("Content-Length") or 0))
        seen.append(json.loads(raw or b"{}"))
        handler.rfile = io.BytesIO(raw)
        answer(handler)

    module.Handler.do_POST = recorded
    server = module.serve(0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    deps.override_ai(ollama=OpenAICompatClient(f"http://127.0.0.1:{server.server_address[1]}/v1", timeout=10))
    yield ai_client, seen
    server.shutdown()
    server.server_close()


def _settled(seen: list, before: int, wait: float = 3.0) -> list[dict]:
    """The requests since `before`, once filing (which runs after the save answers) has sent its own."""
    deadline = time.monotonic() + wait
    while len(seen) == before and time.monotonic() < deadline:
        time.sleep(0.05)
    time.sleep(0.3)
    return seen[before:]


def test_a_note_save_makes_one_small_filing_call(wire):
    client, seen = wire
    for text in ("Bread proving times: 2 hours at 24C", "Harbor launch planned for March"):
        before = len(seen)
        assert client.post("/entries", json={"content": text}).status_code < 300
        sent = _settled(seen, before)
        assert len(sent) == SAVE_CALLS, [r.get("messages", [{}])[0].get("content", "")[:60] for r in sent]
        assert max(len(json.dumps(r)) for r in sent) <= SAVE_BYTES


def test_each_chat_turn_stays_inside_its_wire_budget(wire):
    client, seen = wire
    for text in ("Bread proving times: 2 hours at 24C", "Call Sam about the budget"):
        client.post("/entries", json={"content": text})
    _settled(seen, 0)
    for question, calls, most_bytes, most_tools in TURNS:
        before = len(seen)
        with client.stream("POST", "/chat/stream", json={"question": question}) as response:
            assert response.status_code == 200
            events = [json.loads(line) for line in response.iter_lines() if line]
        sent = seen[before:]
        assert events[-1].get("type") == "done", (question, events[-1])
        assert len(sent) == calls, (question, len(sent))
        assert max(len(json.dumps(r)) for r in sent) <= most_bytes, (question, [len(json.dumps(r)) for r in sent])
        assert max(len(r.get("tools") or []) for r in sent) <= most_tools, question
