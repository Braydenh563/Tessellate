"""Harper on map topic labels (MINDMAP_PLAN VC12): a label with an agreement
error wears a mark, its suggestion is a topic-menu row applied as one Undo
step, and a drag (pointer down) makes no lint call. Measured live in
Chromium (`He have a plan` flagged, "Use “He has a plan”" one Undo step, 0
asks across a 20-step drag), so these hold the wiring."""

from tests._app_js import frontend_text
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
MORE = (JS / "whiteboard-map-more.js").read_text(encoding="utf-8")
MAP = frontend_text("whiteboard-map.js")
BOARD = frontend_text("whiteboard.js")
CSS = (ROOT / "frontend" / "css" / "07-whiteboard-misc.css").read_text(encoding="utf-8")


def test_the_label_is_painted_from_kept_answers_on_every_node_paint() -> None:
    assert "wbMapLazy.paintGrammar(node, d);" in MAP
    paint = MORE[MORE.index("function wbGrammarPaint") : MORE.index("function wbGrammarRepaint")]
    # the paint reads the kept answer and only queues; it never asks
    assert "docGrammarAsk" not in paint
    assert "wbGrammar.found.get(text)" in paint
    assert "wbGrammarSoon()" in paint


def test_only_agreement_lints_are_kept_and_a_drag_asks_nothing() -> None:
    run = MORE[MORE.index("async function wbGrammarRun") : MORE.index("function wbGrammarSoon")]
    assert 'harperKind === "Agreement"' in run
    assert "if (wbGrammar.down) return wbGrammarSoon();" in run
    assert 'addEventListener("pointerdown"' in MORE and 'addEventListener("pointerup"' in MORE


def test_the_fix_is_a_topic_menu_row_and_one_undo_step() -> None:
    assert "wbMapLazy.grammarFixes(mapNode)" in BOARD
    apply = MORE[MORE.index("async function wbGrammarApply") :]
    # wbMapSetNodeStyle pushes the one pushUndo entry for the patch
    assert "await wbMapSetNodeStyle(live, { content:" in apply
    assert "grammarFixes: wbGrammarFixes" in MORE


def test_a_flagged_label_wears_the_documents_double_line() -> None:
    assert ".wb-map-text[data-grammar]" in CSS
    assert "underline double var(--warn)" in CSS
