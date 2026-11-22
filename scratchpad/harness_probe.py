"""INBOX 527: one agent turn against a real model, printed: the tools offered,
every call, the answer. For reading why a turn went the way it did.

    TESSELLATE_EVALS_URL=... TESSELLATE_EVALS_MODEL=... PYTHONPATH=src \
        .venv/bin/python scratchpad/harness_probe.py "Make a note: buy milk" ...
"""
import json
import logging
import os
import sys
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from tessellate.ai import agent
from tessellate.ai.openai_client import OpenAICompatClient
from tessellate.api.app import create_app
from tessellate.ai import wiring  # noqa: F401
from tessellate.core import deps
from tessellate.entry import manager

logging.disable(logging.WARNING)
URL, MODEL = os.environ["TESSELLATE_EVALS_URL"], os.environ["TESSELLATE_EVALS_MODEL"]
data = Path(tempfile.mkdtemp())
deps.init_app_state(data_dir=data)
deps.override_ai(ollama=OpenAICompatClient(base_url=URL))
config = deps.get_config()
config.set_preference("llm_provider", "openai")
config.set_preference("llm_base_url", URL)
config.set_preference("chat_model", MODEL)
(data / "media").mkdir(parents=True, exist_ok=True)
(data / "media" / "wb.png").write_bytes(b"\x89PNG\r\n\x1a\n")
with deps.get_db().session() as s:
    for text, cat in (
        ("Chase up the invoice from the plumber, he still has not sent it", "Work"),
        ("Dentist appointment needs booking, the practice on King Street", "Health"),
        ("Snowdon trip: carry the new boots, start at Pen-y-Pass at 7am", "Travel"),
        ("Planning meeting whiteboard ![whiteboard sketch](/media/wb.png)", "Work"),
    ):
        manager.create_entry(s, text, cat, [])

seen_tools = []
real = agent.tools.ollama_tools


def spy(allowed=None):
    out = real(allowed)
    seen_tools.append([t["function"]["name"] for t in out])
    return out


agent.tools.ollama_tools = spy
client = TestClient(create_app())
for q in sys.argv[1:]:
    seen_tools.clear()
    with client.stream("POST", "/chat/stream", json={"question": q, "use_tools": True}) as r:
        events = [json.loads(line) for line in r.iter_lines() if line]
    print("==", q)
    print("   offered:", seen_tools[0] if seen_tools else None)
    for e in events:
        if e.get("type") == "stats":
            print("    round", e.get("round"), "out tokens", e.get("output_tokens"))
        if e.get("type") in ("tool", "confirm", "limit"):
            print("   ", e.get("type"), e.get("tool") or e.get("name"), e.get("arguments"), e.get("ok"), (e.get("error") or "")[:120])
    print("   answer:", "".join(e.get("delta", "") for e in events if e.get("type") == "answer")[:400].replace("\n", " / "))
