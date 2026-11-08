"""INBOX 1693 (b): a reopened chat draws what the live answer drew.

The live turn saves who wrote the reply (`by`) and its Why trail (`why`); the
loader hands them to the finisher the live path uses (`finishReply`, which
draws the badge, the note card and the Why trail) and gives a model-less reply
its timing line.
"""

from __future__ import annotations

from pathlib import Path

from tests._app_js import app_js_text


def test_the_turn_saves_who_wrote_it_and_why():
    js = app_js_text()
    assert "by: meta && { composed: meta.composed" in js
    assert "why: whyLines," in js


def test_the_loader_redraws_the_badge_card_why_and_timing():
    js = app_js_text()
    start = js.index("Badge and note card as the live answer drew them")
    loader = js[start : start + 1800]
    assert "finishReply(null, { ...by, bubble: handles.bubble, why: message.why" in loader
    assert "message.stats || by" in loader and "message.elapsed_ms" in loader


def test_the_finisher_finds_a_reopened_bubbles_parts_and_draws_the_trail():
    kit = (Path(__file__).resolve().parents[1] / "frontend/js/reply-kit.js").read_text(encoding="utf-8")
    body = kit[kit.index("function replyFinish(") :].split("\n}\n", 1)[0]
    assert 'opts.bubble.querySelectorAll(".bubble-answer")' in body and ".msg-role" in body
    assert "drawWhyTrail(opts.records, opts.why)" in body
