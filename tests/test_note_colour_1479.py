"""INBOX 1479: a note carries a colour of its own, from the capture card's dots.

Before this only a category had a colour (Manage categories). A note's colour is
one of the swatch keys the category picker already uses (routes_categories.py),
stored as the key so the theme decides the shade, never a stored hex.
"""

from __future__ import annotations

import pytest

from tessellate.api.routes_categories import CATEGORY_PALETTE_KEYS
from tessellate.api.schemas import NOTE_COLOURS


def _make(client, **extra):
    response = client.post("/entries", json={"content": "A coloured note", "category": "Ideas", **extra})
    assert response.status_code in (200, 201), response.text
    return response.json()


def test_a_note_has_no_colour_unless_given_one(client):
    assert _make(client)["colour"] is None


def test_a_colour_given_at_creation_is_kept_and_listed(client):
    made = _make(client, colour="teal")
    assert made["colour"] == "teal"
    listed = {row["id"]: row for row in client.get("/entries").json()}
    assert listed[made["id"]]["colour"] == "teal"
    fetched = client.get(f"/entries/{made['id']}").json()
    assert fetched["colour"] == "teal"


@pytest.mark.parametrize("bad", ["chartreuse", "#ff0000", "TEAL", "javascript:1"])
def test_only_a_swatch_key_is_accepted(client, bad):
    response = client.post("/entries", json={"content": "x", "category": "Ideas", "colour": bad})
    assert response.status_code == 422


def test_every_swatch_key_the_card_offers_is_accepted(client):
    for key in NOTE_COLOURS:
        assert _make(client, colour=key)["colour"] == key


def test_an_edit_sets_changes_and_clears_it_and_leaves_it_alone_when_absent(client):
    note = _make(client, colour="red")
    url = f"/entries/{note['id']}"
    other_edit = client.put(url, json={"tags": ["a"]}).json()
    assert other_edit["colour"] == "red"
    changed = client.put(url, json={"colour": "blue"}).json()
    assert changed["colour"] == "blue"
    cleared = client.put(url, json={"colour": None}).json()
    assert cleared["colour"] is None
    refused = client.put(url, json={"colour": "nope"})
    assert refused.status_code == 422


def test_the_note_palette_is_the_category_palette():
    assert NOTE_COLOURS == CATEGORY_PALETTE_KEYS
