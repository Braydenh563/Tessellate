"""D28 (OPEN.md): the next-step chips try a chip by composing its answer, so a turn that already holds
`MAX_CHIPS` answerable chips stops trying the rest (each trial is a whole `compose`, about 5 ms on 500 notes)."""

from datetime import date

from tessellate.ai import composer_chips
from tessellate.api import chat_chips


def test_chips_stop_being_tried_once_the_turn_is_full(monkeypatch):
    chips = [f"Question number {i}?" for i in range(9)]
    tried: list[str] = []

    def lead(chip, notes, today, voice, says_cannot):  # noqa: ANN001
        tried.append(chip)
        return f"answer to {chip}"

    monkeypatch.setattr(chat_chips, "_answer_lead", lead)
    monkeypatch.setattr(chat_chips, "_candidates", lambda result, current, today: [(c, []) for c in chips])
    monkeypatch.setattr(composer_chips, "vocabulary", lambda current, frame: set())
    monkeypatch.setattr(composer_chips, "clean", lambda chip, vocab, titles: chip)
    monkeypatch.setattr(composer_chips, "kind", lambda chip: chip)
    monkeypatch.setattr(composer_chips, "spent", lambda chip, asked: False)
    kept = chat_chips.continue_chips({"text": "x"}, "q", None, [], date(2026, 11, 11), "plain", lambda t: False)
    assert kept == chips[: composer_chips.MAX_CHIPS]
    assert tried == kept, "chips past the limit were composed for nothing"
