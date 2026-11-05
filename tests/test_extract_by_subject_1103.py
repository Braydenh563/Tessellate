"""INBOX 1618: with no model, Extract notes uses the composer's own pieces.

A heading that became the title leaves the body; one long paragraph is cut at
its subject changes; each note is filed and tagged on its own words; no link
runs from a note to its own source text. The extraction reads no clock.
"""
from __future__ import annotations

from tessellate.ai import extractor, no_model_text
from tessellate.entry import manager

UNI = (
    "# Uni is done!! :D\n\nJust finished my final assignment on friday at 3:30am 😭 but it's done haha! "
    "Now I am spending the weekend relaxing and picking up gym properly again since I havent been much "
    "in the last couple weeks because of how busy with assignments I've been relaxing. Played a game of "
    "golf for 18 holes at Windaroo yesterday which was fun but the greens were kinda ass and really dry, "
    "I shot like 130 💀"
)


def _split(text):
    return no_model_text.split_notes(text, extractor.MAX_EXTRACT_NOTES)


def test_a_heading_that_is_the_title_leaves_the_body():
    notes = _split("# Garden\n\nThe garden needs a new path before the spring rain comes.")
    assert [n.title for n in notes] == ["Garden"]
    assert notes[0].content == "The garden needs a new path before the spring rain comes."


def test_a_long_paragraph_splits_at_its_subjects():
    notes = _split(UNI)
    assert len(notes) == 3
    assert "assignment" in notes[0].content and "gym" in notes[1].content and "golf" in notes[2].content
    assert "golf" not in notes[0].content + notes[1].content
    assert not any(n.content.lstrip().startswith("#") for n in notes)


def test_titles_are_short_sentence_case_and_unshouted():
    notes = _split(UNI)
    for note in notes:
        assert 2 <= len(note.title.split()) <= no_model_text.TITLE_WORDS
        assert note.title[0].isupper() and not note.title.endswith(("!", ":D", "."))
    assert "golf" in notes[2].title.lower()


def test_the_split_keeps_every_word_in_order():
    notes = _split(UNI)
    body = UNI.split("\n\n", 1)[1]
    assert " ".join(n.content for n in notes).split() == body.split()


def test_a_short_single_subject_note_stays_one():
    text = "The garden needs a new path. I will lay slabs on the weekend. The path should be wide."
    assert len(_split(text)) == 1


def test_a_long_single_subject_paragraph_stays_one():
    text = " ".join(f"The garden path needs slab number {i} laid flat and then checked with a level." for i in range(6))
    assert len(_split(text)) == 1


def test_never_more_than_the_cap():
    shifts = ["Now", "Then", "Later", "Also", "Next", "Finally"]
    text = " ".join(
        f"{s} the topic{i} number{i} matter{i} needs{i} some{i} careful{i} attention{i} today." for i, s in enumerate(shifts * 2)
    )
    assert len(_split(text)) <= extractor.MAX_EXTRACT_NOTES


def test_each_note_is_filed_on_its_own_words(client, session):
    for text in ("Assignment due for the essay and the exam", "Lecture notes for the unit and assignment", "Study the exam assignment"):
        manager.create_entry(session, text, category_name="Courses & Study", ai_confidence=100)
    for text in ("Golf round at the club, 18 holes", "Golf swing practice on the greens", "Played golf with the club on the weekend"):
        manager.create_entry(session, text, category_name="Sport", ai_confidence=100)
    session.commit()
    body = client.post("/entries/extract/preview", json={"text": UNI}).json()
    by = {("golf" in n["content"]): n["category"] for n in body["notes"]}
    assert by[True] != "Courses & Study"
    assert len(body["notes"]) == 3 and all("tags" in n for n in body["notes"])


def test_no_link_from_a_note_to_its_own_text(client, session):
    source = manager.create_entry(session, UNI)
    session.commit()
    body = client.post("/entries/extract/preview", json={"text": UNI, "source_entry_ids": [source.id]}).json()
    assert not [link for link in body["links"] if link["kind"] == "source"]
    siblings = [link for link in body["links"] if link["kind"] == "sibling"]
    assert len(siblings) == 2
    for link in siblings:
        assert link["reason"] == "Same text, next part" and "!" not in link["reason"] and chr(0x2014) not in link["reason"]


def test_a_selection_from_a_bigger_note_still_links_back(client, session):
    source = manager.create_entry(session, UNI + "\n\nAnd a lot more text about other things entirely.")
    session.commit()
    body = client.post("/entries/extract/preview", json={"text": UNI, "source_entry_ids": [source.id]}).json()
    assert len([link for link in body["links"] if link["kind"] == "source"]) == 3


def test_the_offline_message_says_it_split_by_subject():
    assert "subject" in extractor.offline_message()
    assert "subject" in extractor.SPLIT_FAILED_MESSAGE
