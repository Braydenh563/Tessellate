"""INBOX 1706, the owner on a composer answer in Chat: the Sources and Why buttons
read like the Next chips, their caret sat over the icon, and a reopened chat drew
a different foot and a model-draft warning the live answer never had."""

import re
from pathlib import Path

from tessellate.ai.grounding import composed_support
from tessellate.api.routes_chat import _composed_support
from tessellate.api.routes_conversations import TurnBody, _turn_messages
from tests._app_js import app_js_text

ROOT = Path(__file__).resolve().parent.parent
CSS = (ROOT / "frontend/css/answer-foot-lazy.css").read_text(encoding="utf-8")

ROWS = [
    {"note_id": n, "kind": "note", "said": "quoted", "sentence": f"Orion note number {n} says something about the launch."}
    for n in range(1, 12)
]
ANSWER = "\n\n".join(row["sentence"] for row in ROWS)


def _saved(**extra):
    body = TurnBody(question="what about Orion", answer=ANSWER, sentence_grounding=ROWS, **extra)
    return _turn_messages(body)[1]


def test_a_saved_composer_answer_has_the_support_the_live_one_sent():
    """Live and reload carry one shape: no model-draft notice, every line counted."""
    live = _composed_support({"grounding": ROWS, "support": {"supported": 11, "sentences": 11}})
    saved = _saved(by={"composed": True, "model": ""})["support"]
    assert saved["by_model"] is False and saved["low"] is False
    assert (saved["supported"], saved["sentences"]) == (live["supported"], live["sentences"]) == (11, 11)


def test_a_saved_composer_answer_keeps_the_streams_own_digest_support():
    sent = {"supported": 3, "sentences": 3, "digest": True, "shape": "count", "figure": "3"}
    saved = _saved(by={"composed": True, "model": ""}, support=sent)["support"]
    assert saved["digest"] is True and saved["figure"] == "3" and saved["by_model"] is False


def test_a_model_answer_is_still_recounted_and_keeps_its_notice():
    body = TurnBody(
        question="what about Orion",
        answer="The launch is certainly going to be wonderful. Nothing here comes from any note at all.",
        sentence_grounding=ROWS[:1],
        by={"composed": False, "model": "m"},
        support={"digest": True},
    )
    saved = _turn_messages(body)[1]["support"]
    assert "by_model" not in saved and "digest" not in saved
    assert saved["low"] is True


def test_composed_support_counts_picture_readings_as_before():
    rows = [{"said": "picture", "sentence": "a"}, {"said": "picture", "sentence": "b"}, {"said": "quoted", "sentence": "c"}]
    assert composed_support({"low": False}, rows)["low"] is True


def test_live_and_reopened_turns_count_sources_the_same_way():
    js = app_js_text()
    assert js.count("composed: Boolean(meta?.composed)") == 1
    assert "composed: Boolean(message.by?.composed)" in js
    assert "support: meta?.composed ? groundingSupport : null" in js


def test_the_foot_buttons_are_quiet_text_buttons_not_suggestion_chips():
    js = app_js_text()
    assert 'button.className = "ghost quiet answer-foot-chip"' in js
    assert "chip-interactive answer-foot-chip" not in js
    #: the hit-target overhang of `.chip-interactive::after` was what the caret fought
    caret = re.search(r"\.answer-foot-chip::after \{([^}]*)\}", CSS).group(1)
    assert "position: static" in caret and "opacity" not in caret
    assert re.search(r'\.answer-foot-chip\[aria-expanded="true"\] \{[^}]*background: var\(--ghost-btn-bg\)', CSS)


def test_a_forged_composed_turn_is_stored_with_the_servers_own_notice():
    """Review 5834144051 item 1: the page's support is not trusted."""
    junk = {"by_model": True, "low": True, "supported": 999, "sentences": -4, "evil": "x", "unsupported": ["<b>"], "figure": "y" * 500}
    saved = _saved(by={"composed": True, "model": ""}, support=junk)["support"]
    assert saved["by_model"] is False and saved["low"] is False
    assert (saved["supported"], saved["sentences"]) == (11, 11)
    assert "evil" not in saved and "figure" not in saved and saved["unsupported"] == []
