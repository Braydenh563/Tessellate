"""L127: the document assistant says what it is doing while it waits, from the shared phase table."""

from __future__ import annotations

from pathlib import Path

CODEKIT = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "documents-codekit.js").read_text(encoding="utf-8")


def test_the_assistant_writes_the_reaching_phase_while_the_request_is_out():
    start = CODEKIT.index("async function docAssistAsk(")
    body = CODEKIT[start : CODEKIT.index("function docAssistShow(", start)]
    assert body.index('progressPhaseText("reaching")') < body.index("/code-assist"), "the line is drawn before the request"


def test_the_line_goes_when_the_answer_or_an_error_replaces_the_area():
    start = CODEKIT.index("function docAssistAnswerArea")
    assert "area.replaceChildren();" in CODEKIT[start : start + 200]
