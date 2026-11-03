"""Audit 1028 E38: with no model backend running, the Models page still shows
the suggested downloads with how each fits this computer, so a new student can
choose a model for their laptop before installing Ollama. The cards say so and
their Download buttons wait (disabled, with the reason in the title) instead of
the whole box vanishing. The catalogue and the hardware sizing never needed a
backend (`/models/suggested`, `/models/hardware`), only the page hid them."""

from __future__ import annotations

import re

from tests._app_js import FRONTEND_DIR, frontend_text


def test_the_suggested_box_hides_only_for_a_backend_that_cannot_download():
    js = frontend_text("status.js")
    block = js[js.index('$("suggested-box").classList.toggle(') :][:160]
    assert "supports_pull === false" in block, block
    assert "ollama_running" not in block, block


def test_the_cards_are_drawn_whether_or_not_a_backend_answers():
    js = frontend_text("status.js")
    call = re.search(r"if \(([^\n]*)\) window\.renderSuggested\?\.\(status\);", js)
    assert call, "renderSuggested has no call that is separate from the running branch"
    assert "supports_pull !== false" in call.group(1), call.group(1)


def test_a_download_waits_for_the_backend_and_says_why():
    js = frontend_text("settings-models.js")
    assert "offline: !status.ollama_running" in js
    assert re.search(r"state\.offline[^\n]*\n[^\n]*disabled = true", js) or "primary.disabled = state.offline" in js
    assert "Start Ollama first" in js
    assert "suggested-offline" in js


def test_the_notice_exists_once_in_the_page():
    html = (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")
    tag = re.findall(r'<p id="suggested-offline"[^>]*>', html)
    assert len(tag) == 1, tag
    assert re.search(r'class="[^"]*\bnotice\b', tag[0]), tag[0]
