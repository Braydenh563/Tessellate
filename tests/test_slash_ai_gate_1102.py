"""The slash menu's AI rows follow the model gate like #doc-ai (audit 1102 DX28).

With no model, "Ask Atlas to write here" was drawn at full strength and opened
a bar that could not answer, while #doc-ai beside it was dimmed with the reason.
Both AI rows now name the control that carries their gate (`gate: "doc-ai"`,
whose `data-needs-model` and `data-model-offer` are the one wording), are drawn
dimmed with that control's tooltip when `aiIsOff()`, and a press says why with
the same offer popover instead of running. The chord (Ctrl+J) is not a row: it
still opens the bar, which stays disabled with the reason (DOCUMENTS_PLAN
decision, 2026-10-11).
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EDITOR = (ROOT / "frontend" / "js" / "editor.js").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "css" / "05-sidebars-themes.css").read_text(encoding="utf-8")


def _body(name: str) -> str:
    start = EDITOR.index(f"function {name}(")
    return EDITOR[start: EDITOR.index("\n}\n", start)]


def test_both_ai_rows_name_the_control_that_holds_their_gate() -> None:
    for row_id in ("ai-inline", "ai-edit"):
        start = EDITOR.index(f'id: "{row_id}"')
        assert 'gate: "doc-ai"' in EDITOR[start: EDITOR.index("run:", start)], row_id


def test_a_gated_row_is_drawn_dimmed_with_the_reason() -> None:
    draw = _body("editorRenderMenu")
    assert "item.gate" in draw and "aiIsOff()" in draw
    assert '"aria-disabled"' in draw and "ai-unavailable" in draw
    assert "editor-menu-item.ai-unavailable" in CSS


def test_pressing_a_gated_row_offers_a_model_instead_of_running() -> None:
    run = _body("editorRunItem")
    assert "openModelOffer(gate)" in run
    assert run.index("openModelOffer(gate)") < run.index("editorRememberBlock")
