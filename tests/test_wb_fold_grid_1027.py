"""What a narrow context bar folds into its ⋯ menu is one labelled grid
(INBOX 1403: the owner's screenshot showed Start, End, Medium and Solid as
pills wrapping onto three ragged rows, with Solid alone and indented after a
stray rule). Every group `wbFoldContextBar` can fold carries its own row
label, the caps group is two rows, and the rules that lay the grid out are
the ones the bar's own hairline rule cannot beat.
`scratchpad/ui-sweeps/wb1027-moremenu.js` measures it at 1280, 700 and 390."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
LAZY = (ROOT / "frontend" / "css" / "library-lazy.css").read_text(encoding="utf-8")
WB = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")


def _fold_order() -> list[str]:
    match = re.search(r"const WB_CTX_FOLD = \{ order: \[(.*?)\]", WB)
    assert match, "WB_CTX_FOLD moved"
    return re.findall(r'"(\w+)"', match.group(1))


def test_every_group_that_can_fold_has_a_row_label():
    for name in _fold_order():
        tags = re.findall(rf'<div class="wb-context-group[^"]*" data-wb-ctx="{name}"[^>]*>', HTML)
        assert tags, f"no {name} group in the bar"
        for tag in tags:
            assert "data-fold-label=" in tag or name == "caps", f"{name} folds with no row label: {tag}"


def test_the_caps_group_is_a_start_row_and_an_end_row():
    start = HTML.index('data-wb-ctx="caps"')
    block = HTML[start:HTML.index('data-wb-ctx="stroke"')]
    assert 'class="wb-fold-row" data-fold-label="Start"' in block
    assert 'class="wb-fold-row" data-fold-label="End"' in block
    assert block.index('data-fold-label="Start"') < block.index('id="wb-prop-startcap"') < block.index('data-fold-label="End"') < block.index('id="wb-prop-endcap"')


def test_labels_read_in_sentence_case_with_no_dash():
    for label in re.findall(r'data-fold-label="([^"]+)"', HTML):
        assert label[0].isupper() and label[1:] == label[1:].lower() or " " in label, label
        assert "\u2014" not in label and "!" not in label


def test_the_grid_rules_beat_the_bars_hairline_rule_and_keep_the_bar_unchanged():
    assert ".wb-fold-row,\n.wb-fold-controls {\n  display: contents;" in LAZY
    assert "#wb-context-overflow > .wb-context-group:not(.hidden) {" in LAZY
    assert "grid-template-columns: 3.5rem minmax(0, 1fr);" in LAZY
    assert "content: attr(data-fold-label);" in LAZY
    # The closed face's own Start and End words give way to the row label.
    assert '#wb-context-overflow #wb-prop-startcap ~ .select-opener .select-value::before' in LAZY
