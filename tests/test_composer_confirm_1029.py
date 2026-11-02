"""Confirm cards write what the person typed, in the note's own shape (audit
1029 C40 to C43, INBOX 1357: the class, not the case).

The speller serves the verb and the target only; the free text of an add, a
rename title and a tag is never respelt. An add keeps the note's structure
(a checklist item stays an item), a rename replaces the title line, and
"<item> on the <note>" finds the item on that note.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from tessellate.ai import acts, commands
from tessellate.entry import manager

NOW = datetime(2026, 10, 10, 12, 0)

#: Words the speller would "correct" (oat -> at, lite -> like, ...).
OWN = ["oat milk", "please", "oat flat white", "lite beer", "cheez crackers", "wifi dongle", "tmrw bread", "ur keys"]


@pytest.mark.parametrize("words", OWN)
@pytest.mark.parametrize("frame", ["add {w} to the Lisbon packing list", "append {w} to the Lisbon packing list", "please add {w} to the Lisbon packing list"])
def test_an_add_keeps_the_typed_words(words, frame):
    found = commands.read_typed(frame.format(w=words), NOW)
    assert found and found["intent"] == "append"
    assert found["content"].lower() == words.lower()


@pytest.mark.parametrize("title", ["Atlas wishlist", "Oat milk plan", "Lite reading", "Trip to Lisbon 2027"])
@pytest.mark.parametrize("frame", ["rename the Atlas ideas note to {t}", "retitle the Atlas ideas note as {t}", "rename the note Atlas ideas to {t}"])
def test_a_rename_keeps_the_typed_title(title, frame):
    found = commands.read_typed(frame.format(t=title), NOW)
    assert found and found["intent"] == "rename" and found["title"] == title


@pytest.mark.parametrize("tag", ["oat milk", "lite", "wifi"])
def test_a_tag_keeps_the_typed_word(tag):
    found = commands.read_typed(f"tag the gym note as {tag}", NOW)
    assert found and found["intent"] == "tag" and found["tags"] == [tag.replace(" ", "-")]


def test_a_misspelt_verb_is_still_put_right():
    assert commands.read_typed("delte my old wifi note", NOW)["intent"] == "delete"
    found = commands.read_typed("addd oat milk to the Lisbon packing list", NOW)
    assert found and found["intent"] == "append" and found["content"] == "Oat milk"


@pytest.mark.parametrize(
    ("content", "added", "want"),
    [
        ("# Packing\n\n- [ ] shoes", "oat milk", "# Packing\n\n- [ ] shoes\n- [ ] oat milk"),
        ("# Packing\n\n- [x] shoes\n", "oat milk", "# Packing\n\n- [x] shoes\n- [ ] oat milk"),
        ("# Packing\n\n- [ ] shoes\n\n\n", "- [ ] oat milk", "# Packing\n\n- [ ] shoes\n- [ ] oat milk"),
        ("# Packing\n\n* [ ] shoes", "tea", "# Packing\n\n* [ ] shoes\n- [ ] tea"),
        ("# Buy\n\n- eggs", "oat milk", "# Buy\n\n- eggs\n- oat milk"),
        ("# Idea\n\nA paragraph.", "oat milk", "# Idea\n\nA paragraph.\n\noat milk"),
    ],
)
def test_an_add_keeps_the_notes_structure(content, added, want):
    assert commands.appended(content, added) == want


@pytest.mark.parametrize(
    ("content", "want"),
    [
        ("# Atlas ideas\n\nwhat if", "# Atlas wishlist\n\nwhat if"),
        ("Atlas ideas\nwhat if", "# Atlas wishlist\nwhat if"),
        ("\n\nAtlas ideas", "\n\n# Atlas wishlist"),
        ("## Atlas ideas\nbody", "# Atlas wishlist\nbody"),
    ],
)
def test_a_rename_replaces_the_title_line(content, want):
    assert commands.retitled(content, "Atlas wishlist") == want


def _seed(session):
    manager.create_entry(session, "# Lisbon packing list\n\n- [ ] passport\n- [ ] charger\n- [ ] walking shoes")
    manager.create_entry(session, "# Gym kit\n\n- [ ] charger\n- [ ] towel")
    manager.create_entry(session, "# Atlas ideas\nwhat if the graph clustered by theme?")
    session.commit()


@pytest.mark.parametrize("item", ["charger", "passport", "walking shoes"])
@pytest.mark.parametrize("tail", ["on the Lisbon packing list", "in the Lisbon packing list", "on my Lisbon packing list", "from the Lisbon packing list", "on the Lisbon list"])
@pytest.mark.parametrize("verb", ["tick off", "check off", "cross off"])
def test_an_item_on_a_named_note_is_found(session, item, tail, verb):
    _seed(session)
    planned = acts.preview(session, acts.parse(f"{verb} {item} {tail}", NOW))
    assert planned.get("card"), planned
    step = planned["card"]["steps"][0]
    assert "Lisbon" in str(planned["line"]) and f"[x] {item}" in step["arguments"]["content"]


def test_the_same_item_on_two_notes_is_told_apart(session):
    _seed(session)
    planned = acts.preview(session, acts.parse("tick off charger on the Gym kit", NOW))
    assert "Gym kit" in planned["line"]


def test_the_add_card_writes_an_item_and_the_rename_card_one_title(session):
    _seed(session)
    add = acts.preview(session, acts.parse("add oat milk to the Lisbon packing list", NOW))
    assert add["card"]["steps"][0]["arguments"]["content"].endswith("- [ ] walking shoes\n- [ ] Oat milk")
    ren = acts.preview(session, acts.parse("rename the Atlas ideas note to Atlas wishlist", NOW))
    assert ren["card"]["steps"][0]["arguments"]["content"] == "# Atlas wishlist\nwhat if the graph clustered by theme?"
