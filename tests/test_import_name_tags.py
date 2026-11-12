"""Imported people and places become tags, and more contact shapes are read (L575)."""

from __future__ import annotations

from datetime import datetime

from tessellate.ai import recognise
from tessellate.entry import app_import
from tests.test_app_import import _notes, _post, _zip

NOW = datetime(2026, 11, 12, 10, 0)


def _read(text: str) -> list[tuple[str, str]]:
    return [(s.kind, s.text) for s in recognise.recognise(text, now=NOW) if not s.rank]


def test_name_tags_take_a_few_of_each_kind_as_written():
    names = {"people": ["Ann Lee", "Bo Chan", "Cy Dunn", "Di Fox"], "places": ["Lisbon"]}
    assert app_import.name_tags(names) == ["Ann Lee", "Bo Chan", "Cy Dunn", "Lisbon"]


def test_an_imported_note_gets_the_people_and_places_it_names_as_tags(client):
    vault = _zip({"Trip.md": "# Trip\n\nMeet Priya Raman in Lisbon on Friday to plan the week.\n"})
    ids = _post(client, "obsidian", "vault.zip", vault).json()["ids"]
    note = _notes(client, ids)[0]
    assert {"Priya Raman", "Lisbon"} <= set(note["tags"]), note["tags"]


def test_a_title_before_a_name_makes_it_a_person_and_is_not_part_of_the_name():
    assert ("person", "Sam Patel") in _read("Dr. Sam Patel met Ms Priya Raman")
    assert ("person", "Priya Raman") in _read("Dr. Sam Patel met Ms Priya Raman")
    assert _read("Ask Dr Lee about it") == [("person", "Lee")]


def test_a_phone_number_with_a_home_trunk_zero_or_a_tel_link_is_one_phone():
    assert [(s.kind, s.value) for s in recognise.recognise("+44 (0)20 7946 0958", now=NOW)] == [("phone", "+442079460958")]
    assert [(s.kind, s.value) for s in recognise.recognise("tel:+442079460958", now=NOW)] == [("phone", "+442079460958")]
