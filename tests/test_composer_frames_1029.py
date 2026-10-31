"""Sentence frames are one naming and fragment rule (audit 1029 C1, C2, C3,
C8, C38, C39; INBOX 1420: title-less notes; a fix holds for the class).

- a name or a title keeps its capital wherever a fragment starts;
- a title is named ("your Atlas retro meeting note"), never said as if the
  person said it ("you noted atlas retro meeting");
- "you still need to", "Remind you to" and "you meant to" go only before an
  item that starts with a verb ("you still need to passport" was a noun);
- a title-less note is named by its clipped first clause, and a section of
  one note ("Attendees:", "Pros:") is never named as a note of its own;
- "[[Reading list]]" is said as its title;
- no speech act the note did not make ("you heard that"), and a title or a
  list item is never a "doing" clause ("you were thinking, Fast and Slow").

Every rule runs over three notebooks of the same shapes with different names
and several phrasings, in Ask (`notes_only`) and in Chat, with no model.

Fixed clock: Thursday 29 October 2026, 10:00."""

from __future__ import annotations

import datetime as dt
import re

import pytest

from tessellate.ai import composer_digest
from tessellate.api import routes_chat
from tessellate.core import config
from tessellate.entry import manager
from tests.test_composer_route_688 import _ask

NOW = dt.datetime(2026, 10, 29, 10, 0, 0)
D = dt.datetime

#: (project, three people, a place, a book and its author, a second book).
FAMILIES = [
    ("Atlas", ("Sara", "Tom", "Priya"), "Lisbon", "The Overstory", "Richard Powers", "Thinking, Fast and Slow"),
    ("Beacon", ("Mia", "Raj", "Ola"), "Porto", "Deep Work", "Cal Newport", "Quiet, the Power of Introverts"),
    ("Orion", ("Lena", "Ben", "Kofi"), "Kyoto", "The Hobbit", "Tolkien", "Wild, a Journey on Foot"),
]


def _notes(fam) -> list[tuple[str, dt.datetime]]:  # noqa: ANN001
    project, (a, b, c), place, book, author, second = fam
    return [
        (f"# Project {project} kickoff meeting\n\nAttendees: {a}, {b}, {c}\n\nDecisions: ship the beta by 15 December\n\n"
         f"Actions: {b} to draft the API spec by Friday, {c} to send mockups, book the review room", D(2026, 10, 13, 9)),
        (f"# Project {project} weekly sync\n\nBeta scope is frozen. {a} raised a risk about the timeline.", D(2026, 10, 27, 9)),
        (f"{project} retro meeting", D(2026, 10, 26, 9)),
        (f"# {project} follow-ups\n\n- [ ] {b} to draft the API spec by Friday\n- [ ] {c} to send mockups\n- [ ] book the review room", D(2026, 10, 25, 9)),
        (f"# {place} packing list\n\n- [ ] passport\n- [ ] charger\n- [ ] walking shoes", D(2026, 10, 20, 9)),
        (f"# {place} trip\n\nFlights booked for 5 November. Stay near the old town.", D(2026, 10, 5, 9)),
        (f"# Reading\n\n{book} by {author}: protect long blocks of focus.\n\nIt was a slow start but the stories are beautiful. Check [[Reading list]] later.", D(2026, 10, 10, 9)),
        (f"Reading list\n\n{second}\n{book}", D(2026, 10, 28, 9)),
        (f"Reading: {book} by {author}, a slow start but the stories are beautiful.", D(2026, 10, 11, 9)),
        ("Thinking about whether to move to a four day week.\n\nPros: more time for running and baking\n\nCons: pay cut", D(2026, 10, 21, 9)),
        ("Idea: a bike route along the river to work, about 8 km.", D(2026, 10, 22, 9)),
        ("Key idea: protect long blocks of focus", D(2026, 10, 18, 9)),
        ("# Sourdough starter\n\nA sourdough starter is flour and water left to ferment with wild yeast.", D(2026, 8, 2, 9)),
        ("# Sourdough loaf\n\nBaked a sourdough loaf with a darker crust.", D(2026, 8, 14, 9)),
        (f"Coffee with {a}, she is moving to {place} in spring.", D(2026, 10, 19, 9)),
    ]


def _questions(fam) -> list[str]:  # noqa: ANN001
    project, (a, b, _c), place, _book, _author, _second = fam
    p, pl = project.lower(), place.lower()
    return [
        f"what about project {p}", f"tell me about Project {project}", f"what about {p}", f"tell me about {project}",
        f"what did I write about {b}", f"tell me about {a}", f"what about {a.lower()}",
        f"what do I still need to pack for {pl}", f"tell me about {place}", f"what about {pl}",
        f"what is left on {p} follow-ups", f"tell me about the {p} retro", "what is in my reading list", "what did I read",
        "how about running", "four day week", "what are my ideas", "what about focus", "tell me about sourdough",
        "what is a sourdough starter", "tell me about the kickoff meeting", "what do I need to do",
    ]


@pytest.fixture
def answers(client, session, monkeypatch):
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)

    def build(fam, chat: bool) -> list[tuple[str, str]]:  # noqa: ANN001
        for text, when in _notes(fam):
            entry = manager.create_entry(session, text, "Personal")
            entry.created_at = entry.updated_at = when
        session.commit()
        kw = {} if chat else {"notes_only": True, "answer_from": "notes"}
        return [(q, _ask(client, q, **kw)["text"]) for q in _questions(fam)]

    return build


MODES = pytest.mark.parametrize("chat", [False, True], ids=["ask", "chat"])
FAMS = pytest.mark.parametrize("fam", FAMILIES, ids=[f[0] for f in FAMILIES])


def _bad(found: list[str]) -> None:
    assert not found, "\n\n".join(found)


@MODES
@FAMS
def test_a_wiki_link_is_said_as_its_title(answers, fam, chat):
    _bad([f"{q}\n{a}" for q, a in answers(fam, chat) if "[[" in a or "]]" in a])


@MODES
@FAMS
def test_names_and_titles_keep_their_capital(answers, fam, chat):
    project, people, place, book, _author, second = fam
    names = [project, *people, place, "Project " + project]
    titles = [book, second]
    found = []
    for q, a in answers(fam, chat):
        for name in names + titles:
            for m in re.finditer(rf"\b{re.escape(name)}\b", a, re.I):
                if m.group(0)[0] != name[0] and not a[: m.start()].rstrip().endswith(("**", "#")):
                    found.append(f"{q}: {m.group(0)!r} for {name!r}\n{a}")
    _bad(found)


#: Words in the notebook that are things or people, never a verb's place.
NOUNS = {"passport", "charger", "walking", "pay", "task", "sara", "tom", "priya", "mia", "raj", "ola", "lena", "ben", "kofi"}
FRAMES = re.compile(r"\b(?:still need to|Remind you to|meant to|planned to|set out to|told yourself to|reminded yourself to)\s+(?:try\s+)?(\w+)(\s+\w+)?", re.I)


@MODES
@FAMS
def test_a_verb_frame_only_goes_before_a_verb(answers, fam, chat):
    found = []
    for q, a in answers(fam, chat):
        for m in FRAMES.finditer(a):
            word, nxt = m.group(1).lower(), (m.group(2) or "").strip().lower()
            if word in NOUNS and not (word == "pay" and nxt not in ("cut",)):
                found.append(f"{q}: {m.group(0)!r}\n{a}")
    _bad(found)


#: The labels of sections inside a note: none is a note's name.
SECTIONS = r"(?:attendees|decisions|actions|pros|cons|idea|key idea|deep work|the overstory|the hobbit|untitled)"


@MODES
@FAMS
def test_a_section_or_a_first_word_never_names_a_note(answers, fam, chat):
    found = []
    for q, a in answers(fam, chat):
        if re.search(rf"\b(?:your|the) {SECTIONS}(?: by [\w ]+)? notes?\b", a, re.I) or re.search(r"\buntitled\b", a, re.I):
            found.append(f"{q}\n{a}")
    _bad(found)


@MODES
@FAMS
def test_a_title_is_named_never_spoken(answers, fam, chat):
    project = fam[0]
    titles = [f"{project} retro meeting", f"Project {project} kickoff meeting", f"Project {project} weekly sync", "Sourdough starter", "Sourdough loaf"]
    spoken = r"(?:noted|wrote down|jotted down|said|mentioned|wrote|recorded|put down)(?: that)?"
    found = []
    for q, a in answers(fam, chat):
        for t in titles:
            if re.search(rf"\byou {spoken} {re.escape(t)}\b", a, re.I) or re.search(rf"(?:^|\n){re.escape(t)}, from your note\b", a, re.I):
                found.append(f"{q}: {t}\n{a}")
        if re.search(r"you saved your [\w ]+, an? [\w ]+ (?:is|are) ", a) or re.search(r"\byou (?:noted|wrote down|jotted down) (?:baked|went|made)\b", a):
            found.append(f"{q}\n{a}")
    _bad(found)


@MODES
@FAMS
def test_no_speech_act_the_note_did_not_make(answers, fam, chat):
    found = [f"{q}\n{a}" for q, a in answers(fam, chat) if re.search(r"\byou (?:heard|took away) that\b", a, re.I)]
    _bad(found)


@MODES
@FAMS
def test_a_title_or_a_list_item_is_not_a_doing_clause(answers, fam, chat):
    second = fam[5].split(",")[0]
    found = [f"{q}\n{a}" for q, a in answers(fam, chat) if re.search(rf"\byou were {re.escape(second.lower())}\s*,", a, re.I)]
    _bad(found)


# --- the pieces, alone --------------------------------------------------------------


@pytest.mark.parametrize(("text", "said"), [
    ("Deep Work by Cal Newport", "Deep Work by Cal Newport"),
    ("The Overstory by Richard Powers", "The Overstory by Richard Powers"),
    ("Project Atlas kickoff meeting", "Project Atlas kickoff meeting"),
    ("Baked a loaf", "baked a loaf"),
    ("Invite Daniel to the party", "invite Daniel to the party"),
    ("Check [[Reading list]] later", "check Reading list later"),
    ("See [[Trips|the trip note]]", "see the trip note"),
])
def test_fragment_keeps_a_title_capital_and_lowers_a_word(text, said):
    assert composer_digest._fragment(text, set()) == said


@pytest.mark.parametrize(("item", "led"), [
    ("book the review room", True), ("draft the API spec", True), ("pack the charger", True), ("renew the passport", True),
    ("passport", False), ("walking shoes", False), ("Tom to draft the API spec", False), ("pay cut", False), ("task one", False),
    ("pay the rent", True), ("call the bank", True),
])
def test_verb_led(item, led):
    assert composer_digest._verb_led(item) is led


@pytest.mark.parametrize(("content", "name"), [
    ("I just missed the bus to uni and had to walk all the way in the rain.", "“I just missed the bus to uni”"),
    ("Idea: a bike route along the river to work, about 8 km.", "the note that starts “Idea: a bike route along the river…”"),
    ("Pros: more time\n\nCons: pay cut", "the note that starts “Pros: more time”"),
])
def test_a_title_less_note_is_named_by_its_clipped_first_clause(content, name):
    from tessellate.ai import composer_frame

    assert composer_frame.short_name({"content": content}) == name


@pytest.mark.parametrize(("text", "said"), [
    ("Thinking, Fast and Slow", "Thinking, Fast and Slow"),
    ("Thinking about a four day week", "you were thinking about a four day week"),
    ("Baked a sourdough loaf", "you baked a sourdough loaf"),
    ("Watered the basil", "you watered the basil"),
    ("Tired after the run", "Tired after the run"),
])
def test_a_title_or_a_feeling_is_not_said_as_doing(text, said):
    assert composer_digest._second_person(text) == said


@pytest.mark.parametrize("key", ["learned", "meant"])
def test_one_reporting_verb_and_none_the_note_did_not_make(key):
    said = composer_digest._BASE[key]
    assert len(said) == 1 and not re.search(r"heard|took away|set out", said[0]), said


@pytest.mark.parametrize("body", ["pay cut", "book club on Friday", "passport", "Tom to draft the spec"])
def test_a_noun_is_never_put_after_planned_to(body):
    assert "planned to" not in composer_digest._clause(body, "noted", 0, True)
