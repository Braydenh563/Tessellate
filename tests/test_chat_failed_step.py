"""A failed step in the agent timeline says what failed (INBOX 904 B49).

The step used to read "Failed due to error" whatever happened; the real
message went only to the status line, which is cleared when the person is
looking elsewhere. Source-level, like its neighbours: the suite cannot see
the DOM.
"""

from pathlib import Path

JS = Path(__file__).resolve().parent.parent / "frontend" / "js" / "chat-attach.js"


def test_the_failed_step_names_the_failure() -> None:
    text = JS.read_text(encoding="utf-8")
    assert "Failed due to error" not in text
    assert "timeline.failRunningStep(" in text
    call = text[text.index("timeline.failRunningStep(") :][:260]
    assert "error.message" in text[text.index("timeline.failRunningStep(") - 400 : text.index("timeline.failRunningStep(")]
    assert "Settings, Models" in call
