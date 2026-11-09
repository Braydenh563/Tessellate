"""INBOX 1679 (k), slice 14: the blocks pane reads for a first use.

One purpose line at the top that says what the pane is for and, under the pointer or the keyboard, what the control
there does; "Add block" and "Connect" as worded buttons in a foot that stays where the list ends. The measured side
(counts, heights at 1440 and 390) is `scratchpad/ui-sweeps/diagram-escape.js pan-panel`; this file holds what a diff can break.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
STEPS = (JS / "diagram-steps.js").read_text(encoding="utf-8")
BUILDER = (JS / "diagram-builder.js").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "css" / "diagram-lazy.css").read_text(encoding="utf-8")
HELP = (ROOT / "src" / "tessellate" / "ai" / "help_topics_more.py").read_text(encoding="utf-8")


def _rule(selector: str) -> str:
    start = CSS.index(selector + " {")
    return CSS[start : CSS.index("}", start)]


def test_the_pane_frame_is_made_in_the_lazy_steps_file_and_asked_for_once_by_the_builder():
    assert "function frame(" in STEPS and "diagramModel.steps = { build, sync, frame, next }" in STEPS
    assert BUILDER.count("diagramModel.steps.frame(") == 1
    # The builder file has a 12,000 byte gzip cap: it asks, it does not build.
    assert "dgm-purpose" not in BUILDER and "dgm-foot" not in BUILDER


def test_the_purpose_line_says_what_the_pane_is_and_follows_the_pointer_and_focus():
    assert "Your blocks, in the order the chart flows." in STEPS
    assert "pointerover" in STEPS and "focusin" in STEPS and "pointerleave" in STEPS and "focusout" in STEPS
    # The words are the controls' own titles, so a hover and a screen reader's name never disagree.
    assert "closest?.(" in STEPS and "control?.title" in STEPS


def test_the_foot_has_add_block_and_connect_as_worded_buttons_and_goes_with_the_last_block():
    assert "ph:plus Add block" in STEPS and "ph:arrow-bend-down-right Connect" in STEPS
    assert 'S.foot?.classList.toggle("hidden"' in STEPS
    foot = _rule(".dgm-foot")
    assert "position: sticky;" in foot and "inset-block-end: 0;" in foot


def test_the_new_rules_use_tokens_only_and_no_em_dashes():
    block = CSS[CSS.index(".dgm-purpose {") :][:1600]
    assert not re.search(r"\d+px", block.split("@media")[0].replace("1px solid", "")), block
    dash = chr(0x2014)
    assert dash not in STEPS and dash not in block


def test_the_guide_says_the_pane_in_the_controls_words():
    assert "Add block" in HELP and "Your blocks, in the order the chart flows" in HELP


def test_the_foot_and_the_checklist_do_not_say_the_same_thing_twice():
    # 1679 blind pass: after the first block the checklist and the foot both offered a box and an arrow.
    # Intent unchanged, the checklist now goes at two boxes (DD-10, 1107), so the foot's Connect shows from then on.
    assert 'S.footConnect?.classList.toggle("hidden", lesson && Boolean(S.steps))' in STEPS
    assert 'S.steps?.firstElementChild?.classList.toggle("hidden", m.nodes.length > 0)' in STEPS
    assert "Add a Box" not in STEPS  # sentence case: "Add a box"


def test_handles_shrink_on_a_small_block_an_empty_name_puts_the_label_back_and_the_hint_goes_when_drawing_starts():
    edges = (JS / "diagram-edges.js").read_text(encoding="utf-8")
    # Intent moved (INBOX 1679 m, the owner's later report, merged first): a small block's handles shrink through
    # `handleSize` and lean out of its edge (tests/test_diagram_1679m.py measures the sizes), not through a CSS scale.
    assert "overlay().handleSize(at, full" in edges and "const lean = size < full" in edges
    assert "label.textContent = nameOf(S, key)), render(S)" in BUILDER
    assert 'S.fig.querySelector(":scope > .dgm-hint")?.remove();' in BUILDER


def test_a_quote_or_hash_code_is_not_drawn_as_its_entity():
    draw = (JS / "mermaid-draw.js").read_text(encoding="utf-8")
    assert '["#quot;", "\\ue001", "&quot;"]' in draw and "text.split(stand).join(mark), result.svg)" in draw
