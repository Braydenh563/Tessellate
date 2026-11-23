"""Source text: the behaviour is CSS and front-end script that only a browser renders, and pytest has none, so these pin the rules' text.

L321: the diagram Versions sheet has a Named only switch, shown when it lists both named versions and plain saves."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _versions() -> str:
    text = (ROOT / "frontend" / "js" / "diagram-ai.js").read_text(encoding="utf-8")
    return text[text.index("async function versions(") : text.index("async function compareThem(")]


def test_the_sheet_has_a_named_only_switch_only_when_both_kinds_are_listed():
    body = _versions()
    assert "Named only" in body
    assert "rows.some((r) => r.name) && rows.some((r) => !r.name)" in body


def test_the_switch_hides_the_plain_saves_and_their_heading():
    body = _versions()
    assert 'list.classList.toggle("dgm-versions-named", only.checked)' in body
    css = (ROOT / "frontend" / "css" / "diagram-lazy.css").read_text(encoding="utf-8")
    assert ".dgm-versions-named .dgm-versions-save" in css and ".dgm-versions-named .dgm-versions-head" in css


def test_a_hidden_ticked_save_is_unticked_so_compare_never_uses_what_is_not_shown():
    assert "if (only.checked)" in _versions() and "row.tick.checked = false" in _versions()
