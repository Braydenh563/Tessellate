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
        #: Owner 2026-11-10: a title-less note is named by its first line, quoted ("your note" no longer names it).
        assert line and "“ring the landlord”" in line["text"]


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


# --- Composer audit 2, G8 (1110): the companion's remarks ---

_TODAY = date(2026, 11, 10)
_NOTES = [
    {"id": 1, "content": "First frost this morning, covered the tomatoes", "created_at": "2024-11-10T09:00:00", "category": "Garden", "tags": []},
    {"id": 2, "content": "Harbor launch date\nThe launch is set for the first week of December with the whole team.", "created_at": "2026-11-09T09:00:00", "category": "Work", "tags": []},
    {"id": 3, "content": "Gym routine\nMonday: squats and rows.", "created_at": "2026-09-10T09:00:00", "category": "", "tags": []},
    {"id": 4, "content": "Shopping\n- [ ] milk\n- [ ] eggs\n- [ ] bread\n- [x] tea", "created_at": "2026-11-08T09:00:00", "category": "", "tags": []},
    {"id": 5, "content": "Priya called about the plan for the weekend and Priya will come", "created_at": "2026-11-07T09:00:00", "category": "", "tags": []},
    {"id": 6, "content": "Priya sent photos from the trip to the coast last week", "created_at": "2026-10-28T09:00:00", "category": "", "tags": []},
    {"id": 7, "content": "Priya wants to visit Anna on the weekend after the move", "created_at": "2026-10-20T09:00:00", "category": "", "tags": []},
]
_REMINDERS = [
    {"id": 1, "text": "Email landlord about the leak", "due_at": "2026-11-08", "done": False},
    {"id": 2, "text": "Pay phone bill", "due_at": "2026-11-09", "done": False},
    {"id": 3, "text": "Take bins out", "due_at": "2026-11-10", "done": False},
    {"id": 4, "text": "Dentist", "due_at": "2026-11-13", "done": False},
]


def _remarks():
    return composer_voice.remarks(_NOTES, today=_TODAY, reminders=_REMINDERS, resurfaced=[3])


def test_an_untitled_note_is_quoted_once_as_written():
    otd = next(r for r in _remarks() if r["kind"] == "on_this_day" and r.get("note_id") == 1)
    assert otd["text"].lower().count("first frost") == 1
    assert otd["text"].startswith("On this day in 2024") and "“First frost this morning, covered the tomatoes”" in otd["text"]


def test_a_month_versary_is_said_only_for_one_three_and_six_months():
    texts = [r["text"] for r in _remarks()]
    assert not any("Two months ago" in t for t in texts)


def test_a_word_is_named_as_written_and_an_item_as_written():
    texts = {r["kind"]: r["text"] for r in _remarks()}
    assert "“Priya”" in texts["pattern"] and "“priya”" not in texts["pattern"]
    assert "“milk”" in texts["open"]


def test_overdue_reminders_are_one_remark_and_the_next_few_days_are_named():
    due = [r["text"] for r in _remarks() if r["kind"] == "due"]
    overdue = [t for t in due if "landlord" in t.lower()]
    assert len(overdue) == 1 and "phone bill" in overdue[0].lower() and "overdue" in overdue[0]
    assert any("Take bins out" in t and "today" in t for t in due)
    assert any("Dentist" in t and "Friday" in t for t in due)
    assert len(due) == 3


def test_today_line_survives_a_count_with_no_sampled_note_from_today():
    """The sample holds only the newest notes, so the whole-notebook count can
    say several were written today while none of them is in the sample (a 500
    on /insights/today-line at 5,000 notes)."""
    today = date(2026, 10, 18)
    notes = [{"id": 1, "content": "ring the landlord", "category": "Home", "tags": [], "created_at": "2026-10-10"}]
    for seed in range(12):
        line = composer_voice.today_line(notes, today=today, seed=seed, counts={today: 5})
        assert line and line["text"]
