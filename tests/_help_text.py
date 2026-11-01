"""The Guide's source, as the tests that read it as text mean it: `help_chat.py`
and the table moved out of it (`help_topics_core.py`, AI23)."""

from __future__ import annotations

from pathlib import Path

AI = Path(__file__).resolve().parents[1] / "src" / "tessellate" / "ai"


def help_chat_text() -> str:
    return "\n".join((AI / name).read_text(encoding="utf-8") for name in ("help_chat.py", "help_topics_core.py"))
