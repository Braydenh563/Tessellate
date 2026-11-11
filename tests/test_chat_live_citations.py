"""The Chat tab numbers a grounded answer's records while it streams (INBOX 320).

The Ask sub-tab already did this with `grounding_live`; the Chat tab's own
stream ignored the event, so its numbers arrived with the finished answer.
The behaviour is measured by `scratchpad/ui-sweeps/chatlivecite.js`; this
test holds the wiring the sweep cannot keep honest on its own: the stream
handler exists, the live paint re-places the markers (a paint rebuilds the
step), and the late-bound hook reaches the timeline.
"""

from __future__ import annotations

from tests._app_js import app_js_text


def test_chat_stream_routes_grounding_live_into_the_markers():
    text = app_js_text()
    assert "onGroundingLive: (event) => {\n        t.groundingSentences = event.sentences" in text
    assert "paintHooks.afterAnswerPaint = placeLiveCitations" in text


def test_every_live_paint_of_a_prose_step_replaces_the_markers():
    text = app_js_text()
    assert "function agentTimeline(holder, options = {})" in text
    assert "liveMarkdownRenderer(el, options.afterAnswerPaint || null)" in text
    # The bubble builds the timeline before the stream knows its rows, so the
    # hook is late-bound through an object the stream fills in.
    assert "paintHooks.afterAnswerPaint?.()" in text
    assert "return { bubble, stepsHolder, recordsHolder, groundingHolder, timeline, paintHooks }" in text
