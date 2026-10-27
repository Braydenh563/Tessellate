"""The persona picker is a model control (owner, 2026-10-25): with no model it is
disabled with the reason as its tooltip, and the same status poll that gates
every `data-needs-model` control re-enables it when a model answers."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
CHAT = (ROOT / "frontend" / "js" / "chat.js").read_text(encoding="utf-8")


def test_the_persona_picker_names_why_it_needs_a_model():
    tag = re.search(r'<select id="persona-select"[^>]*>', INDEX).group(0)
    assert "data-needs-model=" in tag and "changes nothing until one is connected" in tag


def test_rebuilding_the_options_keeps_the_reason_while_gated():
    assert "select.dataset.enabledTitle !== undefined" in CHAT
    assert "syncModelGatedControls" in (ROOT / "frontend" / "js" / "status.js").read_text(encoding="utf-8")


def test_the_help_says_the_picker_waits_for_a_model():
    from tessellate.ai import help_chat

    text = " ".join(str(t.get("body", "")) for t in help_chat.HELP_TOPICS if t.get("id") == "notebook-questions")
    assert "persona" in text.lower() and "no model" in text.lower()
