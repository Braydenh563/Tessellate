"""L154: a quote in an answer is the note's own words. The app's re-voicing ("my" to
"your", "I" to "you", a verb moved to the past) belongs to the sentence around a quote,
never inside the quotation marks. Only the first letter's case may differ (a quote
opens a sentence), and a clip may end early with an ellipsis."""

from __future__ import annotations

import re
from datetime import date

import pytest

from tessellate.ai import composer_digest

BODIES = [
    "bake at 230C for 20 min then rest, my oven runs hot",
    "Bake at 230C until golden, I always forget to preheat",
    "call the plumber on monday about my leak",
    "I need to call the plumber on friday",
    "remember to water the plants on tuesday and thursday, my fern is dying",
    "book the flights for next friday, I think my passport is fine",
    "don't forget mum's birthday on 3 March, we are all going",
    "pick up my dry cleaning, I'm late",
]
QUESTIONS = ["what did I write about {t}", "what do my notes say about {t}", "tell me everything about {t}"]
_PERSON = re.compile(r"\b(?:I|my|me|mine|we|our|I'm|I've)\b")


def _check(body):
    notes = [
        {"id": i + 1, "content": f"Chores {i}\n\n{body}", "created_at": f"2026-10-0{i + 2}T10:00:00", "category": "Home", "tags": []}
        for i in range(3)
    ]
    seen = 0
    for template in QUESTIONS:
        said = composer_digest.answer(template.format(t="chores"), notes, today=date(2026, 10, 12))
        for quote in re.findall("“([^”]+)”", (said or {}).get("text", "")):
            seen += 1
            clip = quote.rstrip("…").strip()
            assert clip.lower() in body.lower(), (quote, body)
            #: The person words inside the quote are the writer's, as written.
            for word in _PERSON.findall(body):
                if word in clip.split():
                    assert word in quote.split(), (quote, body)
    return seen


@pytest.mark.parametrize("body", BODIES)
def test_every_quote_is_the_notes_own_words(body):
    _check(body)


def test_the_check_sees_quotes_at_all():
    assert sum(_check(b) for b in BODIES) >= 3
