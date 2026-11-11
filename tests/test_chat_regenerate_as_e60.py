"""Regenerate in another persona, and every regenerate sends `attempt` (audit 1028 E60, E62).

The answer's ⋯ menu offers "Regenerate as..." with one row per persona the
picker lists. It rides the same path as "Regenerate from here": the question
stays, the answer is replaced, and the persona is this turn's only
(`opts.persona`), so the picker is left where the person put it.
"""

from __future__ import annotations

from tests._app_js import JS_DIR


def _read(name: str) -> str:
    return (JS_DIR / name).read_text(encoding="utf-8")


def test_the_answer_menu_offers_regenerate_as_with_a_row_per_persona():
    turn = _read("chat-turn.js")
    assert "regenerateAsItems(bubble)" in turn
    assert "Regenerate as..." in turn
    assert "regenerateFromBubble(bubble, { persona: name })" in turn
    assert '$("persona-select")?.options' in turn


def test_a_submenu_action_sits_in_the_overflow_and_not_in_the_visible_row():
    kit = _read("answer-kit.js")
    assert "actions.filter((action) => !action.items)" in kit
    assert "items: action.items" in kit


def test_the_persona_is_this_turns_and_the_picker_is_not_touched():
    turn = _read("chat-turn.js")
    assert 'const sentPersona = opts.persona || $("persona-select").value' in turn
    edit = _read("chat-edit.js")
    assert "async function regenerateFrom(bubble, opts = {})" in edit
    assert "persona: opts.persona" in edit
    assert 'persona-select").value =' not in edit and 'persona-select").value =' not in turn


def test_regenerate_from_here_sends_an_attempt_that_counts_up_per_question():
    edit = _read("chat-edit.js")
    assert "const attempt = (Number(asked.bubble.dataset.attempt) || 0) + 1;" in edit
    assert "replaceLast: true, attempt" in edit
