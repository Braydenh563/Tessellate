"""The Guide's source, as the tests that read it as text mean it: `help_chat.py`
and the table moved out of it (`help_topics_core.py`, AI23; `help_topics_core_tail.py`, K24)."""

from __future__ import annotations

from pathlib import Path

AI = Path(__file__).resolve().parents[1] / "src" / "tessellate" / "ai"


def help_core_text() -> str:
    """`help_topics_core.py` and the second half moved out of it whole (K24)."""
    return "\n".join((AI / name).read_text(encoding="utf-8") for name in ("help_topics_core.py", "help_topics_core_tail.py"))


def help_chat_text() -> str:
    return (AI / "help_chat.py").read_text(encoding="utf-8") + "\n" + help_core_text()


def agent_text() -> str:
    """The agent loop's source, as the tests that read it as text mean it: the two
    layers moved out of it and the hub (`agent_policy.py`, `agent_turn.py`, AI23)."""
    names = ("agent_policy.py", "agent_turn.py", "agent.py")
    return "\n".join((AI / name).read_text(encoding="utf-8") for name in names)
