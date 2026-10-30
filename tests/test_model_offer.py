"""DOCUMENTS_PLAN 24 row 3 (Brief 76): a model-gated control that answers.

With no model, a control marked `data-model-offer` is `aria-disabled`, not
disabled: a press opens a popover with why, what still works (the
attribute's line) and Set up a model. Measured by `probe76d`-style driving:
the documents' two AI controls each open it and its button opens Settings.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
#: status-panels.js holds the popover since it left the boot scripts (gzip budget).
STATUS = "\n".join((ROOT / "frontend" / "js" / name).read_text(encoding="utf-8") for name in ("status.js", "status-panels.js"))
INDEX = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")


def _body(name: str) -> str:
    start = STATUS.index(f"function {name}(")
    return STATUS[start: STATUS.index("\n}\n", start)]


def test_the_documents_ai_controls_answer_rather_than_refuse():
    for control in ("doc-ai", "doc-ai-run", "draft-compose", "draft-refine", "chat-plan", "template-draft"):
        tag = re.search(rf'<button id="{control}"[^>]*>', INDEX).group(0)
        assert "data-needs-model=" in tag and 'data-model-offer="' in tag, control


def test_the_gate_marks_them_aria_disabled_and_the_press_opens_the_offer():
    assert 'setAttribute("aria-disabled", "true")' in _body("closeModelGate")
    assert "closeModelGate(control)" in _body("syncModelGatedControls")
    assert "openModelGate(control)" in _body("syncModelGatedControls")
    offer = _body("openModelOffer")
    assert "Set up a model" in offer and 'openSettingsModal("models")' in offer
    assert "placeHelpPopover(panel, control)" in offer
    assert '[data-model-offer][aria-disabled="true"]' in STATUS
    assert "stopImmediatePropagation" in STATUS
