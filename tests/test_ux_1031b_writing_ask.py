"""UX review 1031 (M8 to M12, L9 to L11): the Writing room's no-model copy,
its chips' state and diagram preview, and the Ask foot's announcement and hit
area. Measured in the app (a no-model server, 1440 and 390 wide); these hold
the source shape so a later edit cannot undo them quietly."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
CSS = ROOT / "frontend" / "css"


def _js(name: str) -> str:
    return (JS / name).read_text(encoding="utf-8")


def test_the_no_model_banner_and_help_name_only_the_modes_that_need_a_model():
    banner = _js("status.js")
    assert "nothing can be drafted" not in banner
    assert "Only Carry on and Translate need one; the rest works by rule." in banner
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    body = " ".join(html[html.index('id="draft-help-body"'):].split("</div>", 1)[0].split())
    assert "Drafting and Refine need a model" not in body
    assert "Carry on and Translate need a model connected" in body


def test_a_chip_that_needs_no_model_clears_the_needs_a_model_line():
    agent = _js("chat-agent.js")
    click = agent[agent.index("function renderDraftQuickstarts"):agent.index("function markDraftQuickstart")]
    assert click.index('setDraftStatus("");') < click.index("if (aiIsOff() && start.model) setDraftStatus(")
    assert 'setDraftStatus("");' in _js("wiring.js")[_js("wiring.js").index('if (id === "draft-kind")'):][:700]


def test_the_quick_start_chips_expose_their_state_and_include_the_diagram():
    agent = _js("chat-agent.js")
    table = agent[agent.index("const DRAFT_QUICKSTARTS"):agent.index("];", agent.index("const DRAFT_QUICKSTARTS"))]
    assert 'kind: "diagram"' in table and 'label: "Make a diagram"' in table
    assert 'chip.setAttribute("aria-pressed", String(on));' in agent


def test_the_draft_is_announced_as_updated_only_when_it_changed():
    desk = _js("writing-desk.js")
    assert 'if ($("draft-text").value !== draft) announce("The draft has been updated.");' in desk
    assert 'announce("The draft has been updated.");\n' not in desk.replace('!== draft) announce("The draft has been updated.");', "")


def test_a_diagram_pass_is_drawn_under_the_draft_with_the_shared_mermaid_recipe():
    desk = _js("writing-desk.js")
    drawn = desk[desk.index("function drawDraftDiagram"):][:900]
    assert 'ensureModule("mermaid")' in drawn and "mermaidDrawIn(host)" in drawn
    assert "drawDraftDiagram();\n  saveDraftLocally();" in desk
    assert 'id="draft-diagram"' in (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    app = _js("app.js")
    assert 'writingDesk: ["/css/writing-desk-lazy.css", "/js/writing-desk.js"]' in app


def test_the_ask_answer_and_its_foot_are_announced_with_counts():
    ask = _js("capture-ask.js")
    assert "function announceAskFoot()" in ask
    assert ".then(followups).catch(() => {}).then(announceAskFoot);" in ask
    body = ask[ask.index("function announceAskFoot"):ask.index("function renderAskAnswerFoot")]
    for part in ("#ask-answer-related .answer-related-chip", "#ask-answer-sources .chat-source-card", "#ask-followups .chip-interactive", "Answer ready."):
        assert part in body


def test_the_ask_foot_chips_keep_their_hit_area_in_a_lazy_sheet_not_the_boot_ones():
    lazy = (CSS / "ask-compose-lazy.css").read_text(encoding="utf-8")
    assert re.search(r"\.answer-related-chip \{\s*overflow: visible;", lazy)
    coarse = lazy[lazy.index("@media (pointer: coarse)"):]
    assert ".answer-related," in coarse and ".ask-followups" in coarse and "row-gap: calc(var(--target-min) - 1.5rem)" in coarse
    assert (CSS / "writing-desk-lazy.css").exists()
