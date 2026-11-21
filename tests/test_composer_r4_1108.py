"""Composer round 4, 2026-11-08: the rows of audits 1107 (D, E, R3) that were
unfixed or partly fixed when the answers were re-asked on the head. Every
question runs through the digest then the composer, as the route does; no
model, fixed clock (`_seed_r2_1107.TODAY`)."""

from __future__ import annotations

from datetime import date

from tests._seed_r2_1107 import TODAY, _route_answer, ask

assert TODAY == date(2026, 11, 7)


def _pool(*texts: str, ago: int = 0) -> list[dict]:
    day = date.fromordinal(TODAY.toordinal() - ago).isoformat()
    return [{"id": i, "content": t, "category": "Uncategorised", "tags": [], "created_at": f"{day}T10:00:00Z"} for i, t in enumerate(texts, 1)]


def say(question: str, *texts: str, ago: int = 0) -> str:
    return _route_answer(question, _pool(*texts, ago=ago))["text"]


def test_e6_a_limit_in_another_note_is_not_the_budget():
    said = ask("how much is left in my budget", only=("Budget", "Bank", "Car", "Dentist bill"))
    assert said.startswith("I found no budget figure in your notes."), said
    assert "over your" not in said and "$" not in said, said


SARA = (
    "# Sara\n\nSara is my sister. Her birthday is on 14 March.",
    "# Gift ideas\n\nSara wants a jazz record.",
    "Sara likes jazz",
)


def test_r3_4_the_first_note_about_a_subject_is_the_oldest_of_them():
    pool = _pool(*SARA)
    for note, ago in zip(pool, (30, 20, 3), strict=True):
        note["created_at"] = f"{date.fromordinal(TODAY.toordinal() - ago).isoformat()}T10:00:00Z"
    said = _route_answer("what is the first note I wrote about Sara", pool)["text"]
    assert said.startswith("Your first note about Sara is **Sara**, written "), said
    assert "Sara is your sister" in said, said


def test_r3_4_the_last_note_about_a_subject_is_the_newest_of_them():
    pool = _pool(*SARA)
    for note, ago in zip(pool, (30, 20, 3), strict=True):
        note["created_at"] = f"{date.fromordinal(TODAY.toordinal() - ago).isoformat()}T10:00:00Z"
    said = _route_answer("what is the last note about Sara", pool)["text"]
    assert said.startswith("Your latest note about Sara is "), said
    assert "likes jazz" in said, said


def test_r3_4_the_ordinal_reader_is_linear_on_long_runs():
    import time

    from tessellate.ai import composer_small

    for run in ("first note " * 4500, "the first note about " + "a " * 25_000, " " * 50_000, "last note about the " * 2500):
        t0 = time.perf_counter()
        composer_small.ordinal_about(run, [])
        assert time.perf_counter() - t0 < 2.0, run[:30]



def test_e14_a_name_typed_without_its_accents_finds_the_accented_note():
    notes = ("# José García\n\nJosé is my landlord. Phone 020 7946 0999.", "# Gym\n\nSquats on Monday.")
    for question in ("tell me about Jose Garcia", "tell me about Garcia", "who is Jose"):
        said = say(question, *notes)
        assert "landlord" in said and "don't mention" not in said, (question, said)


def test_e12_a_noun_for_the_phone_is_read_beside_the_business():
    notes = ("# Dentist\n\nPhone 020 7946 0011\nDentist check-up on 11 November.", "# Dentist bill\n\nPaid £85 for the check-up.")
    said = say("dentist number", *notes)
    assert said.startswith("Phone 020 7946 0011"), said


def test_d15_a_days_until_a_verb_reads_as_a_sentence():
    said = say("how many days until my passport expires", "# Passport\n\nExpires 12 March 2031. Number is in the safe.")
    assert "expires is" not in said and "The passport expires" in said and "12 March 2031" in said, said


def test_e17_a_date_in_a_note_extended_later_is_this_year():
    pool = _pool("# Running log\n\nRan 6 km on 25 October.")
    pool[0]["created_at"] = "2026-10-14T10:00:00Z"
    pool[0]["updated_at"] = "2026-11-01T10:00:00Z"
    said = _route_answer("when did I last run", pool)["text"]
    assert "25 October 2026" in said or "25 October," in said and "2025" not in said, said
    assert "a year ago" not in said, said


def test_a_spend_on_a_thing_this_week_is_that_things_amount_only():
    """"$84 on groceries this week and $35 on fuel": the window after the
    thing is dropped from its label, so a groceries ask is not the whole note."""
    said = say("how much did I spend on groceries?", "Spent $84 on groceries this week and $35 on fuel.")
    assert "$84" in said and "$119" not in said and "$35 on fuel" not in said.split("Also")[0], said


def test_a_note_named_for_the_spending_verb_is_named_by_its_words():
    said = say("how much did I spend?", "Spent $84 on groceries this week and $35 on fuel.")
    assert "going by Spent:" not in said and "$119" in said, said
