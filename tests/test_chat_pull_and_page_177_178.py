"""L-chat-177 and L-chat-178 (the owner, 2026-10-10).

177: "the notification said it takes a while to pull the first image for searxng but ive already used
multiple times": the first-pull sentence is chosen from whether the image is absent, before the message.
178: "I pressed the ask about this button ... I was on ask mode, shouldnt it have been auto put on agent":
the action turns Agent on when it can run, and says why when it cannot."""

from __future__ import annotations

import re

from tests._app_js import frontend_text


def _fn(text: str, name: str) -> str:
    start = text.index(f"function {name}(")
    return text[start : text.index("\n}\n", start)]


def test_the_first_run_sentence_only_goes_with_an_absent_image():
    web = frontend_text("web-results.js")
    body = _fn(web, "startSearxng")
    assert re.search(r'first \? "Setting SearXNG up[^"]*first run downloads it[^"]*" : "Starting SearXNG…"', body), body
    #: Both callers decide `first` from the engine state they already hold, before the message is written.
    assert 'webEngineInfo?.state === "absent"' in web
    assert '$("searxng-host-state").textContent === "Not installed"' in frontend_text("settings-controls.js")


def test_ask_about_this_switches_to_agent_or_says_why_not():
    results = frontend_text("web-results.js")
    body = _fn(results, "askAboutPage")
    assert "agentModeAvailable()" in body and 'setChatMode("agent")' in body
    assert body.index("agentModeAvailable()") < body.index("sendChatMessage"), "the mode is decided before the send"
    assert "return toast(" in body[body.index("Agent mode needs a model") - 40 :][:60]
