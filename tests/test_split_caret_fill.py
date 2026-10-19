"""INBOX 1337: the Save as note split button's two halves share one fill."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_the_save_split_caret_is_filled_like_its_main_half() -> None:
    """INBOX 1337: kebabMenu's opener is ghost; the Save as note caret drops it."""
    desk = (ROOT / "frontend" / "js" / "writing-desk.js").read_text(encoding="utf-8")
    body = desk[desk.index("function draftSaveMenuInit(") :]
    assert 'opener.classList.remove("icon-only", "ghost");' in body[: body.index("\n}\n")]
