"""Audit 1029 rank 62 (H13): heading order in the Models pane, and a heading
that claimed to be a button.

- Settings, Models, Installed models is an `h3` whose cards named themselves
  with `h5`, so the outline jumped two levels. An installed model's card is
  `h4` under that `h3`; a suggested card stays `h5` under its group's `h4`.
- `#chat-title` was `<h2 role="button">`, a role axe will not allow on a
  heading (`aria-allowed-role`). It is a heading again; Enter and Space still
  rename the chat, and its tooltip says so.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_an_installed_model_card_is_one_level_under_its_h3() -> None:
    text = (ROOT / "frontend" / "js" / "settings-models.js").read_text(encoding="utf-8")
    card = text.split("function buildModelCard(model, state)", 1)[1].split("\n}\n", 1)[0]
    assert 'document.createElement(model.listed === "installed" ? "h4" : "h5")' in card
    assert 'listed: "installed"' in text, "the installed list marks its cards"


def test_the_chat_title_is_a_heading_without_a_button_role() -> None:
    page = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    tag = re.search(r'<h2 id="chat-title"[^>]*>', page).group(0)
    assert "role=" not in tag
    assert 'tabindex="0"' in tag and "Click to rename" in tag
    wiring = (ROOT / "frontend" / "js" / "wiring.js").read_text(encoding="utf-8")
    assert '$("chat-title").addEventListener("keydown"' in wiring, "the keyboard still renames it"
