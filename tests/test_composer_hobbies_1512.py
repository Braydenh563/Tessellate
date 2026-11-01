"""INBOX 1512 (the owner, 2026-11-01): "still needs better social skills,
grammar and variation". With no model, "Summarise my notes in Hobbies."
quoted first-person link reasons raw ("the mouse is used as my gaming mouse
on my laptop"), kept a reason's capital after a colon ("Shared Tuesday 9pm
legs training"), read a caption as "says a picture of X depicts", spliced
a sentence into a frame ("It also has the split follows this structure"),
said "Your note says" with no note named, used the same frame for every
group ("go together", "You linked X to Y:"), named one title-less note by
its opening three times, and had no line saying what the threads are."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime

import pytest

from tessellate.api import routes_chat
from tessellate.core import config
from tessellate.entry import manager
from tests import _hobbies_1512 as hobbies

NOW = datetime(2026, 11, 1, 12, 0)
QUESTION = "Summarise my notes in Hobbies."


@pytest.fixture
def notebook(session, monkeypatch):
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)
    made = []
    for content, tags, when, _links in hobbies.NOTES:
        entry = manager.create_entry(session, content, "Hobbies", tags)
        entry.created_at = datetime.fromisoformat(when)
        made.append(entry)
    session.commit()
    for (_c, _t, _w, links), entry in zip(hobbies.NOTES, made, strict=True):
        for i, reason in links.items():
            manager.create_link(session, entry, made[i], reason=reason)
    session.commit()
    return made


def _ask(client, question: str) -> str:
    body = {"question": question, "answer_from": "notes", "notes_only": True, "use_tools": False}
    text = []
    with client.stream("POST", "/chat/stream", json=body) as response:
        assert response.status_code == 200
        for line in response.iter_lines():
            if line.strip():
                event = json.loads(line)
                if event["type"] == "answer":
                    text.append(event["delta"])
    return "".join(text)


@pytest.mark.skipif(not os.environ.get("COMPOSER_1512_DUMP"), reason="dump, run by hand")
def test_dump(client, notebook):
    print("\n" + _ask(client, QUESTION))


#: Words quoted in “...” are the owner's own; everything else is the app's.
_QUOTE = re.compile(r"“[^”]*”")


def defects(text: str) -> list[str]:
    """Each defect class of the owner's answer, found in an answer's text."""
    plain = _QUOTE.sub("“”", text)
    found = []
    if re.search(r"\b(?:my|mine|me|myself|I|I'm|I've)\b", plain):
        found.append("first person outside a quote")
    if re.search(r"(?<!\w): (?:Shared|They|The|Both)\b", plain):
        found.append("capital after a colon")
    if re.search(r"\bdepicts\b|(?:says|that|saved [^,.]+,)\s+“?an? (?:picture|photo)\b", plain, re.I):
        found.append("caption read as speech")
    if re.search(r"\bhas (?:the|this|my|your) \w+ (?:follows|is|are|goes|looks)\b", plain):
        found.append("sentence spliced after has")
    if re.search(r"\b[Yy]our note says\b", plain):
        found.append("unnamed note says")
    if "![" in text:
        found.append("markdown image as a name")
    if text.count("go together") > 1 or len(re.findall(r"\bYou linked\b", text)) > 1:
        found.append("same frame each group")
    if text.count("I just bought a new gaming mouse") > 1 or text.count("the note that starts") > 1:
        found.append("one note named in full twice")
    if re.search(r"random ass sketches", plain):
        found.append("slang reason not quoted as theirs")
    return found


def _lead(text: str) -> str:
    return text.split("\n\n", 1)[0]


def _untagged() -> list[dict]:
    notes = hobbies.notes()
    for note in notes:
        note["tags"] = []
    return notes


@pytest.mark.parametrize("notes", [hobbies.notes, _untagged], ids=["tagged", "linked only"])
def test_the_owners_hobbies_summary_reads_as_english(notes):
    from tessellate.ai import composer_digest

    text = composer_digest.answer(QUESTION, notes(), today=hobbies.TODAY)["text"]
    assert defects(text) == [], text


def test_the_summary_reads_as_english_through_the_route(client, notebook):
    text = _ask(client, QUESTION)
    assert defects(text) == [], text


def test_the_lead_names_the_threads():
    from tessellate.ai import composer_digest

    lead = _lead(composer_digest.answer(QUESTION, hobbies.notes(), today=hobbies.TODAY)["text"])
    assert all(word in lead for word in ("gaming", "art", "gym")), lead


def test_a_caption_is_said_as_what_the_picture_shows():
    from tessellate.ai import composer_digest

    text = composer_digest.answer(QUESTION, hobbies.notes(), today=hobbies.TODAY)["text"]
    assert "shows a black gaming mouse" in text and "shows a cartoon cat" in text, text


def test_a_sentence_label_is_said_as_the_notes_words():
    from tessellate.ai import composer_digest

    text = composer_digest.answer(QUESTION, hobbies.notes(), today=hobbies.TODAY)["text"]
    assert "the split follows this structure: squats" in text, text


@pytest.mark.parametrize(("reason", "said"), [
    ("the mouse is used as my gaming mouse on my laptop", "the mouse is used as your gaming mouse on your laptop"),
    ("Shared Tuesday 9pm legs training", "shared Tuesday 9pm legs training"),
    ("I use it for work and we share it", "you use it for work and we share it"),
    ("Both offer conversation starters", "both offer conversation starters"),
    ("Lisbon trip packing", "Lisbon trip packing"),
    ("they are both random ass sketches lol", "“they are both random ass sketches lol”"),
    ("I'm hyped for this one lol", "“I'm hyped for this one lol”"),
])
def test_a_link_reason_is_said_in_the_second_person_or_quoted_as_theirs(reason, said):
    from tessellate.ai import composer_frame

    assert composer_frame.reason_said(reason) == said


@pytest.mark.parametrize(("caption", "said"), [
    ("A photo depicts a black gaming mouse on a desk", "a black gaming mouse on a desk"),
    ("a picture of a gaming mouse depicts its side buttons", "a gaming mouse"),
    ("The image depicts a pencil sketch of a dragon", "a pencil sketch of a dragon"),
    ("a cartoon cat drawn in black pen", "a cartoon cat drawn in black pen"),
])
def test_a_caption_loses_its_frame(caption, said):
    from tessellate.ai import composer_threads

    assert composer_threads.caption_said(caption) == said


def test_the_group_frames_vary_from_group_to_group():
    from tessellate.ai import composer_frame

    notes = hobbies.notes()
    lines = [composer_frame.group_line(g, notes, "hobbies", i=n) for n, g in enumerate(composer_frame.groups(notes))]
    openings = [re.sub(r"\b(?:gaming|art|gym)\b", "X", line.split(":")[0]) for line in lines]
    assert len(set(openings)) == len(openings), lines


def test_a_link_inside_a_named_pair_refers_back_to_them():
    from tessellate.ai import composer_frame

    notes = hobbies.notes()
    line = composer_frame.group_line(next(g for g in composer_frame.groups(notes) if 1 in g.ids), notes, "hobbies")
    assert line.count("I just bought a new gaming mouse") == 1 and "them" in line, line
