"""A category for a note that is not saved yet (INBOX 1330).

The Capture box already offers tags while you type (`/entries/suggest-tags`);
this is the other half of "a live, inline organization suggestion": the
category the notebook's own words point to, with the reason, with no model and
no write. Nothing is offered where the words know nothing: a guess shown as a
choice costs a glance, but a category with no reason behind it is noise.

Since INBOX 1583 the draft's filing offer is the note editor's
(`POST /read/offers`, `lexical_filing.filing_call`): Capture drew a second
chip from `/entries/suggest-category` beside it ("File under Hobbies" next
to "File in Hobbies"), each picking by its own rule. The route is gone; the
intent of each test here is unchanged.
"""

from __future__ import annotations


def _filing(client, content: str, title: str = "") -> dict:
    """The draft's first filing offer, in the shape the old route answered."""
    found = client.post("/read/offers", json={"content": content, "title": title}).json()["offers"]
    first = next((o for o in found if o["kind"] == "filing"), None)
    return {"category": first["value"]["category"], "reason": first["reason"]} if first else {"category": None, "reason": ""}


def _seed(client):
    for text in (
        "Simmer the tomato sauce for an hour, add basil and garlic",
        "Sourdough starter: feed it flour and water, bake the loaf hot",
        "Roast chicken with lemon, garlic and thyme, rest it before carving",
    ):
        client.post("/entries", json={"content": text, "category": "Cooking"})
    for text in (
        "Squat day: five sets, deadlift next, bench on Friday",
        "Gym session: pull day, rows and curls, stretch after",
        "Running plan: easy miles, one long run, rest on Sunday",
    ):
        client.post("/entries", json={"content": text, "category": "Fitness"})


def test_a_draft_gets_the_category_its_words_point_to_with_the_reason(client):
    _seed(client)
    body = _filing(client, "Roast the potatoes with garlic and a little thyme")
    assert body["category"] == "Cooking"
    assert body["reason"], "a suggestion without its reason is not offered"


def test_the_title_counts_with_the_first_line(client):
    _seed(client)
    body = _filing(client, "five sets, then rest", title="Deadlift and squat session")
    assert body["category"] == "Fitness"


def test_words_the_notebook_does_not_know_offer_nothing(client):
    _seed(client)
    for content in ("", "   ", "Zebra quokka nebula fjord"):
        body = _filing(client, content)
        assert body == {"category": None, "reason": ""}


def test_nothing_is_written_and_no_model_is_asked(client):
    from tessellate.core import deps

    _seed(client)
    before = client.get("/entries").json()
    client.post("/read/offers", json={"content": "Simmer the sauce for an hour with basil"})
    after = client.get("/entries").json()
    assert after == before
    assert deps.get_ollama().chat_calls == []
