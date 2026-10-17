"""B80: with no model, a note can be offered a tag the notebook has never
used, named for the subject the note's own words name (`ai/tagging.new_topics`);
the notebook's own tags still come first, and one passing word is not a topic."""

from __future__ import annotations

from tessellate.ai import tagging
from tessellate.entry import manager


def _suggest(client, content: str, tags: list[str] | None = None) -> dict:
    return client.post("/entries/suggest-tags", json={"content": content, "tags": tags or []}).json()


def test_a_note_in_an_empty_notebook_is_offered_the_subject_it_names(client):
    got = _suggest(client, "Did squats and deadlifts at the gym this morning")
    assert "fitness" in got["suggested_tags"], got
    assert "gym" in got["suggested_tag_reasons"]["fitness"]


def test_one_passing_word_is_not_a_topic(client):
    assert _suggest(client, "Dentist on Tuesday about the crown")["suggested_tags"] == []
    assert _suggest(client, "Grocery list: milk and eggs")["suggested_tags"] == []


def test_a_tag_the_note_already_has_is_not_offered_again(client):
    got = _suggest(client, "Did squats and deadlifts at the gym this morning", ["Fitness"])
    assert "fitness" not in [t.casefold() for t in got["suggested_tags"]]


def test_the_notebooks_own_tags_come_first_and_a_new_one_fills_the_rest(client, session):
    manager.create_entry(session, "Trip notes: flights and a hotel for the trip", "Travel", ["holiday"])
    session.commit()
    got = _suggest(client, "Booked flights, a hotel and the trip itself; also python unit tests and the api")["suggested_tags"]
    assert got[0] == "holiday" and "software" in got, got
    assert len(got) <= tagging.TAG_LIMIT


def test_a_sensitive_subject_is_never_invented_as_a_tag(session):
    named = tagging.new_topics(session, "Chemotherapy and an oncologist appointment for the cancer scan", [])
    assert named == []
