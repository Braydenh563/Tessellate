"""INBOX 720 (the owner, 2026-10-06): "I accidentally pressed ctrl v randomly
on the app when on the ask tab and it started captioning the image". A board
still showing in the Library kept its view and canvas un-hidden while another tab
was on screen, so the board's document-level paste took the image. The board
answers a paste only while its canvas is rendered. And the Ask history's
buttons are rounded squares like every other quiet icon button."""

from __future__ import annotations

from pathlib import Path

JS = Path("frontend/js/whiteboard-commands.js").read_text(encoding="utf-8")
CSS = Path("frontend/css/01-forms-settings.css").read_text(encoding="utf-8")


def test_board_commands_live_only_while_the_canvas_is_rendered() -> None:
    body = JS[JS.index("function wbCommandsLive()") :]
    body = body[: body.index("\n}\n")]
    assert "canvas.getClientRects().length" in body


def test_ask_history_icon_buttons_are_rounded_squares() -> None:
    rule = CSS[CSS.index("\n.icon-btn {") :]
    rule = rule[: rule.index("\n}\n")]
    assert "border-radius: var(--radius-md);" in rule
    assert "radius-pill" not in rule


def test_a_confirm_sits_above_the_lightbox() -> None:
    """INBOX 721: Delete from the lightbox opened its confirm behind it."""
    import re

    chat = Path("frontend/css/02-chat-graph.css").read_text(encoding="utf-8")
    lightbox = chat[chat.index("\n.lightbox {") :]
    lightbox_z = int(re.search(r"z-index:\s*(\d+)", lightbox[: lightbox.index("\n}\n")]).group(1))
    confirm = CSS[CSS.index(".modal-overlay.confirm-overlay {") :]
    confirm_z = int(re.search(r"z-index:\s*(\d+)", confirm[: confirm.index("\n}\n")]).group(1))
    assert confirm_z > lightbox_z
