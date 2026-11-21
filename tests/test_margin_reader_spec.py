"""The margin reader (WORLD_CLASS_PLAN 15, I2; 18, H8): a second reader in the
editor, from the person's own notes.

`POST /editor/read` takes one paragraph and returns at most three typed
cards: `repeats`, `contradicts`, `answers`, `date`, `related`. Without a model
it answers from the notebook alone (keyword and meaning search, the open
questions, the date reader); with `judge` and a model it asks the model for
the relation. Nothing is ever written into the text.
"""

from __future__ import annotations

from tessellate.ai import margin
from tessellate.core import deps
from tessellate.core.database import DerivedFact


def _note(client, text: str) -> int:
    response = client.post("/entries", json={"content": text, "category": "Home"})
    assert response.status_code == 201, response.text
    return response.json()["id"]


BOILER = "The boiler service is booked with Hendry Heating every October before the cold weather."
RENT = "The flat rent is 900 pounds a month and is paid on the first of the month."


def test_at_most_three_cards(client):
    for n in range(6):
        _note(client, f"Boiler pressure note {n}: the boiler pressure gauge reads low again in the hallway cupboard.")
    response = client.post("/editor/read", json={"paragraph": "The boiler pressure gauge reads low in the hallway cupboard again."})
    assert response.status_code == 200
    cards = response.json()["cards"]
    assert 1 <= len(cards) <= 3
    # Never the same source twice in one answer.
    assert len({c.get("source_entry_id") for c in cards}) == len(cards)


def test_a_repeated_paragraph_is_a_repeat_of_that_note(client):
    source = _note(client, BOILER)
    _note(client, "Groceries for the week: oats, apples and coffee beans.")
    cards = client.post("/editor/read", json={"paragraph": BOILER}).json()["cards"]
    assert cards[0]["kind"] == "repeats"
    assert cards[0]["source_entry_id"] == source
    start, end = cards[0]["source_span"]
    assert end > start


def test_the_note_being_written_is_never_its_own_card(client):
    own = _note(client, BOILER)
    cards = client.post("/editor/read", json={"entry_id": own, "paragraph": BOILER}).json()["cards"]
    assert all(c.get("source_entry_id") != own for c in cards)


def test_a_changed_number_is_a_contradiction_without_a_model(client):
    source = _note(client, RENT)
    cards = client.post(
        "/editor/read", json={"paragraph": "The flat rent is 950 pounds a month and is paid on the first of the month."}
    ).json()["cards"]
    assert cards[0]["kind"] == "contradicts"
    assert cards[0]["source_entry_id"] == source


def test_a_negation_is_a_contradiction_under_the_fake_model(ai_client, fake_ollama):
    source = _note(ai_client, "Batch size should stay at 32 for the vision training runs on the lab cluster.")
    fake_ollama.librarian_reply = "contradicts - one says keep it, the other says change it"
    response = ai_client.post(
        "/editor/read",
        json={"paragraph": "For vision training on the lab cluster we will raise the batch to 128.", "judge": True},
    )
    body = response.json()
    assert body["judged"] is True
    kinds = {(c["kind"], c.get("source_entry_id")) for c in body["cards"]}
    assert ("contradicts", source) in kinds


def test_an_open_question_answered_by_the_paragraph(client, session):
    asker = _note(client, "Is the API subscription worth the monthly cost for the side project?")
    session.add(DerivedFact(entry_id=asker, kind="question", text="Is the API subscription worth the monthly cost?", confidence=0.9))
    session.commit()
    cards = client.post(
        "/editor/read",
        json={"paragraph": "The API subscription is worth the monthly cost: it saved me ten hours this month."},
    ).json()["cards"]
    answer = [c for c in cards if c["kind"] == "answers"]
    assert answer and answer[0]["source_entry_id"] == asker


def test_a_date_becomes_a_date_card_with_a_parsed_time(client):
    cards = client.post("/editor/read", json={"paragraph": "Call the landlord about the window on Thursday at 3pm."}).json()["cards"]
    dated = [c for c in cards if c["kind"] == "date"]
    assert dated
    assert dated[0]["when"][:4].isdigit() and "T" in dated[0]["when"]


def test_with_the_model_down_it_never_waits_on_the_model(client, monkeypatch):
    """`judge` with the model down answers from the notebook and never waits.

    Proved by what is called, not by the wall clock (L-world-class-199: 3.39 s
    on a loaded CI runner against a 1.5 s bound, with the probe itself 2 us):
    one reachability probe, no chat, no retry. The measured number is in the
    CHANGELOG.
    """
    for n in range(30):
        _note(client, f"Note {n} about the garden shed roof, the felt, the gutters and the water butt.")

    class DownModel:
        probes = 0

        def is_running(self):
            DownModel.probes += 1
            return False

        def chat(self, *args, **kwargs):
            raise AssertionError("the margin reader called a model that is down")

    monkeypatch.setattr(deps, "get_ollama", DownModel)
    response = client.post("/editor/read", json={"paragraph": "The shed roof felt is lifting near the gutter.", "judge": True})
    assert response.status_code == 200
    body = response.json()
    assert body["judged"] is False
    assert body["cards"], "the notebook alone still answers"
    assert DownModel.probes == 1


def test_the_switch_turns_it_off(client):
    from tessellate.ai import facts

    facts.set_switches(deps.get_config(), {"margin_reader": False})
    body = client.post("/editor/read", json={"paragraph": BOILER}).json()
    assert body == {"cards": [], "judged": False, "off": True}


def test_cards_are_computed_never_stored(client, session):
    _note(client, BOILER)
    before = session.query(DerivedFact).count()
    client.post("/editor/read", json={"paragraph": BOILER})
    assert session.query(DerivedFact).count() == before
    assert margin.MAX_CARDS == 3


def test_the_margin_card_is_on_its_recipe():
    """DESIGN.md's recipe index: a margin card is a quiet `--surface-2` group
    with no border, and the margin is a column of the editor's own row."""
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    css = (root / "frontend" / "css" / "09-editor.css").read_text(encoding="utf-8")
    card = re.search(r"\.doc-margin-card \{(.*?)\}", css, re.S).group(1)
    assert "var(--surface-2)" in card and not re.search(r"\bborder(-(top|left|right|bottom))?\s*:", card)
    html = (root / "frontend" / "index.html").read_text(encoding="utf-8")
    wrap = html.split('id="doc-source-wrap"', 1)[1].split('id="doc-preview"', 1)[0]
    assert 'id="doc-margin"' in wrap
    assert 'id="doc-margin-reader"' in html


def test_the_same_sentence_in_two_notes_is_one_card(client):
    _note(client, RENT)
    _note(client, RENT)
    cards = client.post(
        "/editor/read", json={"paragraph": "The flat rent is 950 pounds a month and is paid on the first of the month."}
    ).json()["cards"]
    assert [c["kind"] for c in cards].count("contradicts") == 1, cards
