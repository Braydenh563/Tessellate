"""L230: Chat with no model answers a sum, a conversion, a date and a week summary, and makes a
reminder from the words alone (the card is confirmed, then the reminder exists)."""

import pytest
from sqlalchemy import select

import tests._seed_r9_1109 as sd
from tessellate.core.database import Reminder
from tests._consent import confirmed


@pytest.fixture
def chat(client, session, monkeypatch):
    sd.seed(session)
    go = sd.asker(client, monkeypatch, chat=True)

    def run(question):
        text, events = go(question)
        done = confirmed(client, list(events))
        return "".join(e.get("delta", "") for e in done if e.get("type") == "answer") if done != events else text

    return run


@pytest.mark.parametrize(
    ("question", "said"),
    [
        ("what is 15% of 240", "36"),
        ("convert 5 miles to km", "8.05 kilometres"),
        ("how many days until Christmas", "25 December"),
        ("summarise my week", "notes in the last seven days"),
    ],
)
def test_sums_conversions_dates_and_the_week_need_no_model(chat, question, said):
    assert said in chat(question)


def test_a_reminder_from_words_is_made(chat, session):
    before = len(session.scalars(select(Reminder)).all())
    text = chat("remind me to call mum on Friday at 9am")
    session.expire_all()
    assert len(session.scalars(select(Reminder)).all()) == before + 1, text
