"""L-documents-18: a template on a diagram that has blocks can replace the diagram (Undo brings it back)
as well as add its blocks as ghosts. Source reads; the measured run is named in HISTORY."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _suggest() -> str:
    return (ROOT / "frontend" / "js" / "diagram-suggest.js").read_text(encoding="utf-8")


def test_receive_takes_a_replace_flag_that_treats_the_pane_as_blank():
    body = _suggest()
    assert "async function receive(S, h, source, said, replace = false)" in body
    assert "const blank = replace || !S.source.trim()" in body


def test_the_template_dialog_offers_replace_only_on_a_pane_with_blocks():
    body = _suggest()
    dialog = body[body.index("async function templates(") : body.index("// --- From my notes")]
    assert "Replace the diagram" in dialog
    assert "fill && !S.plain" in dialog
    assert "use(true)" in dialog
    assert 'chosen.source, `Replaced the diagram with the ${chosen.name.toLowerCase()} template.`, true' in dialog


def test_the_guide_names_the_replace_button():
    text = (ROOT / "src" / "tessellate" / "ai" / "help_topics_more.py").read_text(encoding="utf-8")
    assert "Replace the diagram" in text
