"""The Guide's source, as the tests that read it as text mean it: `help_chat.py`
and the table moved out of it (`help_topics_core.py`, AI23; `help_topics_core_tail.py`, K24)."""

from __future__ import annotations

from pathlib import Path

AI = Path(__file__).resolve().parents[1] / "src" / "tessellate" / "ai"


def after_path(text: str) -> str:
    """The answer without its leading click path (the owner, 2026-11-12, L725: the path leads, then one sentence from the help)."""
    paras = text.split("\n\n")
    keep = [p for p in paras[:1] if p.startswith(("My reading", "Reading that", "I read that"))]
    rest = paras[len(keep):]
    if rest and rest[0].startswith("**Where:** ") and len(rest) > 1:
        rest = rest[1:]
    return "\n\n".join(keep + rest)


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


def help_more_text() -> str:
    """`help_topics_more.py` and the middle block moved out of it whole (K24)."""
    return "\n".join((AI / name).read_text(encoding="utf-8") for name in ("help_topics_more.py", "help_topics_more_mid.py"))
