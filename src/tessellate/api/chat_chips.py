"""The chips under a composed answer, made to continue the conversation (fable-composer-1110 F5).

`continue_chips` takes the composer's own next questions, cleans their subjects against the
notes, puts the frame's questions first (`ai/composer_chips`), and keeps only a chip that is
new to this chat (not the question just asked, not one asked before, and one whose answer is
not an answer already given) and that the composer can answer on the notes it read. A chip
that acts ("Remind me the day before") is kept as text: pressing it asks, and the usual
Confirm card does the rest. Used by the composed answer and the model's draft alike.
"""

from __future__ import annotations

import logging

from tessellate.ai import composer, composer_chips, grounding

_log = logging.getLogger("tessellate.chat")
#: Chips that act or open: not tried against the notes.
_NOT_TRIED = ("Open ", "Remind me", "What else is on that", "Tomorrow", "Friday", "In an hour", "Which is higher")


def _asked(history: list[dict] | None, question: str) -> list[str]:
    return [question, *(str(t.get("question") or "") for t in history or [] if isinstance(t, dict))]


def _given(history: list[dict] | None, text: str) -> set[str]:
    return {composer_chips.lead(str(t.get("answer") or "")) for t in history or [] if isinstance(t, dict)} | {composer_chips.lead(text)}


def _answer_lead(chip: str, notes: list[dict], today, voice: str, says_cannot) -> str | None:  # noqa: ANN001
    """The first line `chip` would be answered with on `notes`, "" for a chip that acts or opens
    (not tried), None when the composer has no answer for it."""
    if chip.startswith(_NOT_TRIED) or not notes:
        return ""
    try:
        trial = composer.compose(chip, notes, today=today, voice=voice)
    except Exception:  # noqa: BLE001 - a chip that cannot be tried is not offered
        _log.warning("a follow-on chip could not be tried, so it is not offered: %r", chip, exc_info=True)
        return None
    text = str(trial.get("text") or "")
    return composer_chips.lead(text) if trial.get("grounding") and not says_cannot(text) else None


def _candidates(result: dict, current: list[dict], today) -> list[tuple[str, list[dict]]]:
    """(chip, the notes to try it on): the frame's questions on the notes it names, then the composer's own."""
    frame, ids = result.get("frame") or {}, set((result.get("frame") or {}).get("note_ids") or [])
    scope = [n for n in current if n.get("source_id", n.get("id")) in ids] or current
    own = composer_chips.frame_chips(frame, current, str(result.get("text") or ""), today.isoformat())
    return [*((c, scope) for c in own), *((c, current) for c in result.get("next") or []), *((c, current) for c in composer_chips.week_chips(frame, today.isoformat()))]


def continue_chips(result: dict, question: str, history: list[dict] | None, current: list[dict], today, voice: str, says_cannot) -> list[str]:  # noqa: ANN001
    """The chips to send under `result`, at most `MAX_CHIPS`."""
    vocab = composer_chips.vocabulary(current, result.get("frame") or {})
    titles = {composer_chips.norm(n.get("title") or "") for n in current}
    asked, given = _asked(history, question), _given(history, str(result.get("text") or ""))
    kept: list[str] = []
    for chip, notes in _candidates(result, current, today):
        if len(kept) >= composer_chips.MAX_CHIPS:
            break  # a full turn tries no more: each trial is a whole compose (D28)
        chip =composer_chips.clean(chip, vocab, titles)
        if not chip or composer_chips.kind(chip) in {composer_chips.kind(k) for k in kept} or composer_chips.spent(chip, asked):
            continue
        said = _answer_lead(chip, notes, today, voice, says_cannot)
        if said is None or (said and said in given):
            continue
        given.add(said)  # two chips with one answer are one chip
        kept.append(chip)
    return kept[: composer_chips.MAX_CHIPS]


def shows_first(composed: dict) -> bool:
    """Whether the composed draft is sent ahead of a model's answer (`composed_preview`): it must quote the notes
    and not be mostly the app's reading of pictures, since that draft would flash a claim the notebook does not
    make (P1). The judgement is `grounding.composed_support`'s, the one that marks the finished answer."""
    rows = composed.get("grounding") or []
    return bool(rows) and not grounding.composed_support(composed.get("support"), rows)["low"]
