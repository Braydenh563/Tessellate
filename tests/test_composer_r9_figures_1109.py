"""R9-10 and R9-13 (composer audit round 9): a comparison ranks the figure on the line that names each side,
an age is worked out from "Born April 2019", and the brief a running model reads keeps the sentence that
holds the question's word. Seed: `tests/_seed_r9_1109.py`."""

from __future__ import annotations

import pytest

import tests._seed_r9_1109 as sd
from tessellate.ai import composer, composer_digest


@pytest.fixture
def say(client, session, monkeypatch):
    sd.seed(session)
    go = sd.asker(client, monkeypatch)
    return lambda q: go(q)[0]


def test_the_cheaper_side_is_ranked_by_its_own_line(say):  # R9-10
    text = say("which is cheaper, Japan or Portugal")
    assert text.startswith("Portugal is cheaper: £1,100 against £2,400 for Japan")


def test_an_age_is_worked_out_from_the_birth_month(say):  # R9-10
    assert say("how old is Pickle").startswith("Pickle is 7 (born April 2019)")


def _notes():
    return [{"id": i + 1, "content": body if title is None else f"# {title}\n\n{body}", "title": title or "", "created_at": f"2026-10-0{1 + i % 9}T10:00:00"}
            for i, (title, body, _ago) in enumerate(sd.NOTES)]


@pytest.mark.parametrize(("question", "needle"), [
    ("why is my bread dense", "longer proof"),
    ("what have I written about meditation", "Skipped meditation"),
])
def test_the_brief_keeps_the_sentence_with_the_questions_word(question, needle):  # R9-13
    made = composer.brief(question, _notes())
    assert made and needle in " ".join(n["content"] for n in made["notes"])


def test_a_composers_denial_is_not_handed_over_as_app_facts():  # R9-13
    assert composer_digest.exact("what do I spend on insurance", [{"id": 1, "content": "Pickle is our cat.", "title": "Pickle"}]) is None
