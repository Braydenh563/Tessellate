"""The spelling menu's candidate rows are words, not five identical commands
(DOCUMENTS_PLAN, "the suggestion menu draws the same check icon on every one of
its five word rows"). Measured 2026-11-12 on port 8794 for "recieve": five rows
(receive, relieve, believe, received, receives), 0 icons on every row, the first
carrying `doc-suggest-best`. The check stays on the suggested-change menu's
Accept rows (`docSuggestMenuItems`), where it means "accept"."""

from __future__ import annotations

from tests._app_js import frontend_text


def test_a_candidate_row_is_bare_text_with_the_first_marked_best():
    src = frontend_text("documents.js")
    start = src.index('answerRows.filter((row) => row.kind === "candidate").forEach((row) => {')
    block = src[start : src.index("});", start)]
    assert "item.textContent = row.label;" in block
    assert "doc-suggest-best" in block
    assert "ph:" not in block and "setLabel" not in block and "createElement(\"i\")" not in block
