"""INBOX 1518, audit 1031 N20: the note card's menu taxonomy is one rule.
AI actions hold every act Atlas does, Connect holds links and places, Add
holds what is attached to the note."""

from __future__ import annotations

import re
from pathlib import Path

TEXT = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "entry-menu.js").read_text(encoding="utf-8")


def _group(name: str) -> str:
    """The source of one menu group's array."""
    start = TEXT.index(f"const {name} = [")
    return TEXT[start : TEXT.index("\n  ];\n", start)]


def _labels(source: str) -> set[str]:
    return {m.group(1) for m in re.finditer(r'label: [^"\n]*"ph:[a-z-]+ ([^"]+)"', source)}


def test_ai_actions_hold_every_act_atlas_does():
    ai = _labels(_group("aiItems"))
    #: L763, the owner 2026-11-12 (newer than INBOX 1518): Similar, Add context
    #: and Continue thought are acts the AI does, so they moved here.
    assert {"Explain this note", "Make a mind map", "Ask Atlas about this note", "Translate", "Remove title", "Similar notes", "Add context", "Continue thought"} <= ai
    assert not ai & (_labels(_group("connectItems")) | _labels(_group("addItems")))


def test_connect_holds_links_and_places_and_add_holds_what_attaches():
    connect, add = _labels(_group("connectItems")), _labels(_group("addItems"))
    assert {"Add to a document", "Add to a board or map", "Link to another", "Copy wiki link", "Referenced by", "Show in graph"} <= connect
    assert {"Properties", "Remind me", "Attach a file"} <= add
    assert not connect & {"Properties", "Ask Atlas about this note", "Explain this note"}


def test_a_private_note_still_gets_no_model_acts_but_keeps_the_group_for_what_stays_local():
    ai = _group("aiItems")
    assert "...(entry.is_private ? [] : [" in ai
    assert "if (aiItems.length) menu.appendChild(buildMenuGroupButton(\"ph:sparkle AI actions\", aiItems))" in TEXT


def test_a_source_card_does_not_say_the_title_twice():
    """Audit 1031 N14 (INBOX 1518): the card's head is the title, so the body starts after the title line."""
    root = Path(__file__).resolve().parents[1] / "frontend" / "js"
    ask = (root / "citation-peek.js").read_text(encoding="utf-8")
    assert "function citationTitleEnd(text, title)" in ask
    assert "citationPeekText(content, source.start, source.end, title.textContent)" in ask
    # The evidence card fills from the row's text, then again from the whole note (INBOX 1525
    # review, item 7: a passage past the row's 300 characters); both fills pass the title.
    assert "citationPeekText(text, g.start, g.end, title)" in (root / "answer-kit.js").read_text(encoding="utf-8")
