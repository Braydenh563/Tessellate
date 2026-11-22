"""L716 (F6, owner decision 11 first half): the no-model money and checklist figures are exact.
Ten questions on the 1110 notebook: each figure is the notes' own, summed or counted by the app.
The model-on side of the comparison needs a real model (the row says what is left)."""

import pytest

import tests._seed_composer_1110 as sd
from tests import _seed_1031c as c


@pytest.fixture
def chat(client, session, monkeypatch):
    sd.seed(session)
    return c.asker(client, monkeypatch, chat=True)


@pytest.mark.parametrize(
    ("question", "said"),
    [
        ("how much did the dentist cost", "$180"),
        ("what did the car service cost", "$420"),
        ("what is the Japan trip budget", "$4,500"),
        ("total cost of the dentist and car service", "$600"),
        ("how much did the dentist and the car service cost in total", "$600"),
        ("how much do the dentist and the car service cost together", "$600"),
        ("how many items are left on the shopping list", "Three of four"),
        ("how many things are ticked off on my todo list", "One of four"),
        ("what is left on my todo list", "3 still to do on Todo"),
        ("is the bread bought", "Yes"),
    ],
)
def test_the_no_model_figures_are_the_notes_own(chat, question, said):
    assert said in chat(question)[0]
