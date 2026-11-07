"""The chat's way onward, and the two surfaces that lost it.

The suite cannot open a browser, so these are the DOM-shaped facts held as
text: one function draws the Resume and Edit-step buttons, both the live path
and the reopen path call it, and the state it needs is saved with the turn.
"""

from __future__ import annotations

from pathlib import Path
from tests._app_js import app_js_text

ROOT = Path(__file__).resolve().parent.parent
#: app.js plus palette.js: the popup agent (Ctrl+K) was split out of app.js
#: on 2026-09-24, and these tests read it wherever it lives.
APP = app_js_text() + "\n" + (
    ROOT / "frontend" / "js" / "palette.js"
).read_text(encoding="utf-8")


def test_one_function_draws_the_resume_controls() -> None:
    assert "function appendRunResumeControls(bubble, spec)" in APP


def test_both_paths_draw_them_through_that_function() -> None:
    """Reported: the buttons "arent persistent and disappeared when I came
    back to the chat". The live stream built them from its own variables and
    the reopen path did not build them at all, which is the same shape the
    Sources panel, the grounding chips and the followups were each fixed in.
    Two call sites, so a fix to one is a fix to both."""
    assert APP.count("appendRunResumeControls(") >= 3, (
        "expected the definition plus a call from the live path and one from "
        "openConversation"
    )
    assert "...message.resume," in APP, "the reopen path rebuilds them from the saved state"


def test_the_saved_turn_carries_the_state_only_when_there_is_one() -> None:
    """An ordinary answer has nowhere to resume to, and should not write five
    null fields onto every row in the notebook to say so."""
    assert "resumeState.stoppedAtStep !== null ||" in APP
    assert "? resumeState" in APP


def test_the_status_bar_names_the_scope_not_the_persona() -> None:
    """The dock button beside "Ask" read "Atlas", so the bar offered two
    buttons that both mean "talk to the AI". The word is the scope now and the
    name is in the tooltip, which also survives renaming the persona."""
    assert 'word.textContent = "Guide";' in APP
    assert "Ask ${guideName} how this app works" in APP


def test_the_popup_agent_writes_its_thinking_as_it_arrives() -> None:
    """Reported: "the popup agent doesnt stream thinking ... the thinking only
    shows up after the response is finished". It was accumulated and prepended
    at the end because the box is closed, which is true of the box and beside
    the point for the wait, where the reasoning is the only thing to show."""
    #: The app's one Thinking fold (INBOX 457), open as it is built, and put
    #: under the bubble's head, inside the step column, never `prepend`ed onto
    #: the bubble above the name and avatar.
    assert "thinkingBox = thinkingFold();" in APP
    #: Placed in the step column where it arrived (B5), still never above the head.
    assert "placeStep(thinkingBox);" in APP
    assert "agentMsg.prepend(" not in APP
    #: Closed when the answer lands, so a finished turn still reads answer
    #: first, and never drawn twice.
    assert "thinkingBox.open = false;" in APP


def test_the_guide_reads_a_stream_and_can_fall_back() -> None:
    #: The Guide's chat moved from settings.js to help-chat.js (a lazy bundle).
    settings = (
        __import__("pathlib").Path(__file__).resolve().parent.parent
        / "frontend" / "js" / "help-chat.js"
    ).read_text(encoding="utf-8")
    assert "async function helpChatStreamTurn({ pending, signal, body, line = null })" in settings
    assert 'api.stream("/help/ask/stream"' in settings
    #: The one-shot route stays as the fallback for a proxy that buffers.
    assert 'return apiJson("/help/ask", {' in settings
    #: **The thinking is the chat transcript's own reasoning block, not a
    #: clipped div** (INBOX 287, the owner: "the thinking box doesnt properly
    #: render in it either at least while streaming"). This line used to pin
    #: `className = "help-chat-think muted"`, a bare `<div>` that CSS clipped
    #: to `max-height: 2.6em`: measured mid-stream at 29px tall over 262px of
    #: text, unlabelled, with no way to open it. The shape is pinned here
    #: rather than the class name so the next change has to keep the summary
    #: and the body, which are what make it readable.
    #: Now the app's one Thinking fold (`thinkingFold`, INBOX 457), which
    #: carries the summary and the scrolling body by construction.
    assert "const think = thinkingFold();" in settings
    #: Painted through the one renderer (`thinkingPaint`, INBOX 489), which
    #: sets the reasoning as Markdown and keeps the newest line in view.
    assert "thinkingPaint(think, thinkRaw);" in settings
    #: Folded when the answer starts, the same move the chat's own
    #: `foldEarlierThinking` makes, so the answer is not read underneath it.
    assert "if (think.open && !text) think.open = false;" in settings
