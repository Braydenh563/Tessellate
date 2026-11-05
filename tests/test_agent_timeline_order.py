"""CHAT_PLAN B5 (the owner, 2026-11-05): "also in that test request the
search appeared after the generated text when it happened before that text
was written out". Steps and text keep the order they arrived in, one
timeline, in the popup agent as in Chat (the Guide runs no tools)."""

from __future__ import annotations

import json
from pathlib import Path

JS = Path(__file__).resolve().parent.parent / "frontend" / "js"


def test_text_then_a_tool_then_text_arrives_in_that_order(ai_client, fake_ollama):
    ai_client.post("/entries", json={"content": "a note about soaking beans"})
    rounds = iter(
        [
            ("Let me look through your notes.", [{"name": "search_notes", "arguments": {"query": "beans"}}]),
            ("Your note says to soak them overnight.", []),
        ]
    )

    def stream(model, messages, tools, mode=None):
        text, calls = next(rounds)
        yield {"content_delta": text}
        yield {
            "final": {
                "content": text,
                "thinking": None,
                "tool_calls": calls,
                "raw_tool_calls": [{"function": c} for c in calls],
                "stats": dict(fake_ollama.stats, model=model),
                "streamed": True,
            }
        }

    fake_ollama.chat_tools_stream = stream
    with ai_client.stream("POST", "/chat/stream", json={"question": "what about beans?", "use_tools": True}) as response:
        events = [json.loads(line) for line in response.iter_lines() if line.strip()]
    order = []
    for event in events:
        kind = event["type"]
        if kind in ("answer", "tool") and (not order or order[-1] != kind):
            order.append(kind)
    assert order[:3] == ["answer", "tool", "answer"], order


def test_the_popup_agent_places_each_step_where_it_arrived():
    """The popup drew one answer box and put every step fold above it, so a
    search made after the first sentence read as if it came first, and its
    web cards were appended under all the text at the end. Each step now goes
    where it happened (`placeStep`): before the answer box while that box is
    empty, after it once it has words, and the next words open a new box."""
    palette = (JS / "palette.js").read_text(encoding="utf-8")
    assert "const placeStep = (node) => {" in palette
    assert "stepsHolder.insertBefore(stepsFold, answerBox);" not in palette
    assert "placeStep(stepsFold);" in palette and "placeStep(thinkingBox);" in palette
    #: A web fold under its step, not under the whole reply.
    assert "drawAnswerPanels(stepsHolder, [{ web: event.sources }], answerBox)" not in palette
    #: Copy, citations and the reply finish see every box.
    assert "finishReply(answerBoxes," in palette
    assert "addInlineCitations(answerBoxes," in palette
