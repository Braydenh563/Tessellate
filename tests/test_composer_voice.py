"""The app's voice (`ai/composer_voice.py`): every remark grounded, the
companion never twice the same, the phrasebook in the app's copy rules."""

from __future__ import annotations

from datetime import date

from tessellate.ai import composer_voice
from tests import _voice_eval

EM_DASH = chr(0x2014)


def test_every_surface_is_wholly_grounded():
    table = _voice_eval.run()
    for surface, row in table.items():
        assert row["grounded"] == 1.0, (surface, row.get("failures"))


def test_companion_never_says_the_same_thing_twice_in_twenty_days():
    table = _voice_eval.run()
    assert table["companion"]["count"] == 20
    assert table["companion"]["distinct"] == 20
    assert table["companion"]["words"] <= 30


def test_phrasebook_keeps_the_copy_rules():
    for key, text in composer_voice.VOICE.items():
        assert EM_DASH not in text and "!" not in text, key
        assert "Oops" not in text, key


def test_deterministic():
    data = _voice_eval.load()
    today = date.fromisoformat(data["today"])
    a = composer_voice.remarks(data["notes"], today=today)
    b = composer_voice.remarks(data["notes"], today=today)
    assert [r["text"] for r in a] == [r["text"] for r in b]


def test_title_from_own_words_and_none_for_a_heading():
    assert composer_voice.title_for("# Already titled\nbody") == ""
    title = composer_voice.title_for("Remember to ring the landlord about the boiler on Tuesday.")
    assert title == "Ring the landlord about the boiler"


def test_question_detection():
    assert composer_voice.asks("when is the harbor launch?")
    assert not composer_voice.asks("harbor launch")
    assert not composer_voice.asks("tag:work")


def test_today_line_rotates_with_its_seed_and_stays_grounded():
    """INBOX 1300: the line under the greeting varies by seed (same seed, same
    words), every draw traced to the notes. One sentence only (the owner,
    2026-10-18: the sub line must not run long), so six openings, no tail."""
    data = _voice_eval.load()
    today = date.fromisoformat(data["today"])
    notes = _voice_eval.notes_until(data, today)
    draws = [composer_voice.today_line(notes, today=today, seed=s) for s in range(20)]
    assert all(d for d in draws)
    assert len({d["text"] for d in draws}) >= 5
    assert all(d["text"].count(". ") == 0 and len(d["text"]) <= 120 for d in draws)
    again = composer_voice.today_line(notes, today=today, seed=3)
    assert again["text"] == draws[3]["text"]
    for d in draws:
        assert EM_DASH not in d["text"] and "!" not in d["text"]
        assert not _voice_eval.trace(d, notes, today)


def test_today_line_names_an_untitled_note():
    """CI 5783f9d: a note with no heading is named "your note from ...", a
    phrase of the answer's phrasebook the voice's lacked (a 500 on the dashboard)."""
    today = date(2026, 10, 18)
    notes = [{"id": 1, "content": "ring the landlord", "category": "Home", "tags": [], "created_at": "2026-10-18"}]
    for seed in range(6):
        line = composer_voice.today_line(notes, today=today, seed=seed)
        assert line and "your note" in line["text"].lower()


def test_today_line_with_untitled_notes_never_says_the_latest_your_note():
    """UX audit 2026-10-18: "Already today, twelve notes, the latest your note
    from today." The count ends the sentence when the newest note has no title."""
    today = date(2026, 10, 18)
    notes = [
        {"id": i, "content": f"ring the landlord {i}", "category": "Home", "tags": [], "created_at": "2026-10-18"}
        for i in range(1, 13)
    ]
    for seed in range(6):
        text = composer_voice.today_line(notes, today=today, seed=seed)["text"]
        assert "the latest your" not in text and "the newest your" not in text
        assert "twelve" in text.lower()


def test_headline_does_not_repeat_the_sub_line_count():
    from tessellate.ai import greeting_compose as g

    phrases = [p for p, _ in g._context_phrases(g.NotebookFacts(total=40, today=12), "morning")]
    assert not any("12" in p and "today" in p for p in phrases)
