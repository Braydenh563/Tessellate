"""Short lines with a figure are facts the composer can quote (audit 1028 E5).

"Rent 650." was dropped as a two-word fragment, so "how much is my rent"
had nothing to answer from.
"""

from datetime import date

from tessellate.ai import composer

NOTES = [{"id": 1, "content": "# Budget October\n\nRent 650. Groceries 180. Phone 20. Spent 45 on a textbook.",
          "created_at": "2026-10-28"}]


def test_a_word_and_a_figure_is_quoted():
    text = composer.compose("how much is my rent", NOTES, today=date(2026, 10, 28))["text"]
    assert "Rent 650" in text


def test_a_lone_word_is_still_noise():
    assert not composer._short_fact("Booked.")
    assert not composer._short_fact("Ideas")
    assert composer._short_fact("Rent 650.")
    assert composer._short_fact("Wifi: hunter2")
