"""Offers, kinds and clips (audit 1029 rank 53; C4, C5, C9, C10, C15, C16).

The class, not the cases:

- an offer is a next step on what was just said, so its to-do comes from a
  note the answer cites (it was "Remind you to buy a capo?" under an answer
  about a sister);
- the kind of thing reviewed is the one the notes name (a book was "your only
  film review"), and a book is read, not watched;
- one clip for every name, label and title: it cuts at a word, with an
  ellipsis, and never ends on a dangling "the" or "of";
- a time phrase carries its own preposition ("on 20 October", "in October")
  and a leading "Tomorrow" is lowered when a frame puts it mid-sentence.

Fixed clock: Thursday 29 October 2026."""

from __future__ import annotations

from datetime import date

import pytest

from tessellate.ai import composer_compose, composer_digest, realise
from tessellate.ai import recognise as rec

TODAY = date(2026, 10, 29)
RAW = [
    ("# Guitar\n\n- [ ] buy a capo\n- [ ] restring the guitar", "2026-10-15", "Hobbies", ["guitar"]),
    ("# Sister\n\nMy sister's birthday is on 3 December. She likes the sourdough I make.", "2026-10-14", "Family", ["family"]),
    ("# The Overstory\n\nI gave it 4 out of 5. Loved the trees, but the start was slow.", "2026-10-12", "Books", ["books"]),
    ("# Dune\n\nWatched Dune Part Two. 7 out of 10, the sound design was incredible.", "2026-10-12", "Films", ["films"]),
    ("# Piano\n\nGave the album 3 out of 5, a bit thin.", "2026-10-11", "Music", ["album"]),
]
NOTES = [
    {"id": i + 1, "content": c, "created_at": f"{d}T10:00:00", "category": cat, "tags": t}
    for i, (c, d, cat, t) in enumerate(RAW)
]


def _say(question: str) -> dict:
    found = composer_digest.answer(question, NOTES, today=TODAY)
    assert found, question
    return found


@pytest.mark.parametrize(("question", "noun", "verb"), [
    ("what did I think of The Overstory", "book", "read"),
    ("what did I think of Dune", "film", "watch"),
    ("how was The Overstory", "book", "read"),
    ("what did I think of the album", "album", "listen to"),
])
def test_a_review_names_what_was_reviewed(question, noun, verb):
    found = _say(question)
    text = found["text"]
    wrong = {"film", "book", "album"} - {noun}
    assert not [w for w in wrong if f"{w} review" in text], text
    if found.get("offer"):
        assert found["offer"]["label"] == f"Start a list of {noun}s to {verb} next?", found["offer"]


def test_a_review_that_names_nothing_is_a_note_not_a_film():
    notes = [{"id": 1, "content": "# Trip\n\nI gave it 4 out of 5. Loved the food.", "created_at": "2026-10-12T10:00:00", "category": "Trips", "tags": []}]
    found = composer_digest.answer("what did I think of the trip", notes, today=TODAY)
    assert found
    assert "film" not in found["text"] and "film" not in (found.get("offer") or {}).get("label", ""), found


def test_an_offer_only_comes_from_a_note_the_answer_cites():
    out = composer_digest._Out()
    views = {n["id"]: n for n in NOTES}

    class View:
        def __init__(self, note):
            self.note, self.id = note, note["id"]

    class Fact:
        def __init__(self, note):
            self.view = View(note)

    facts = [Fact(views[1]), Fact(views[2])]
    out.rows.append({"note_id": 2})
    kept = composer_digest._answered(out, facts)
    assert [f.view.id for f in kept] == [2]
    out.rows.clear()
    assert composer_digest._answered(out, facts) == facts


@pytest.mark.parametrize("question", [
    "what is my sister's birthday", "what does my sister like", "tell me about my sister", "what did I write about my sister",
    "what do I need to buy", "tell me about the guitar",
])
def test_no_offer_is_about_a_note_the_answer_did_not_use(question):
    found = _say(question)
    offer = found.get("offer") or {}
    if offer.get("kind") != "reminder":
        return
    cited = {g["note_id"] for g in found["grounding"]}
    wanted = offer["text"].lower()
    sources = {n["id"] for n in NOTES if wanted.split(" ", 1)[-1] in n["content"].lower()}
    assert sources & cited, (question, offer, cited)


@pytest.mark.parametrize(("title", "limit", "cut"), [
    ("Met Dana at the meetup, follow up with her by email next week", 30, "Met Dana at the meetup, follow up…"),
    ("Buy a capo and restring the guitar before the gig on Friday", 25, "Buy a capo and restring…"),
    ("short", 30, "short"),
    ("Remember to ring the dentist about the", 100, "Remember to ring the dentist about the"),
])
def test_cut_title_cuts_at_a_word_and_never_dangles(title, limit, cut):
    got = realise.cut_title(title, limit)
    assert got.rstrip("…").split()[-1].lower() not in realise._DANGLING or got == title, got
    if len(title) <= limit:
        assert got == title
    else:
        assert got.endswith("…") and title.startswith(got[:-1].rstrip()), got
        assert len(got) <= limit + 1, got


@pytest.mark.parametrize("words", [["a", "plan", "for", "the"], ["follow", "up", "with", "her", "by"], ["one", "two"]])
def test_drop_dangling_ends_on_a_content_word(words):
    kept = realise.drop_dangling(list(words))
    assert kept and kept[-1].lower() not in realise._DANGLING


@pytest.mark.parametrize(("phrase", "said"), [
    ("20 October", "on 20 October"),
    ("friday", "on friday"),
    ("october", "in october"),
    ("15 to 20 October", "from 15 to 20 October"),
    ("past week", "in the past week"),
    ("yesterday", "yesterday"),
    ("last week", "last week"),
    ("since 3 October", "since 3 October"),
    ("3 days ago", "3 days ago"),
])
def test_a_time_phrase_carries_its_own_preposition(phrase, said):
    assert rec.adverbial(phrase) == said


@pytest.mark.parametrize("span", ["Tomorrow", "Today", "Yesterday", "Tonight"])
def test_a_deictic_day_is_lowered_mid_frame_and_kept_leading(span):
    assert composer_compose._fill("Here is {span}.", {"span": span}) == f"Here is {span.lower()}."
    assert composer_compose._fill("{span} is clear.", {"span": span}) == f"{span} is clear."
    assert composer_compose._fill("Here is {span}.", {"span": "Friday 30 October"}) == "Here is Friday 30 October."


def _citation_names(contents: list[str]) -> list[str]:
    import json
    import shutil
    import subprocess
    from pathlib import Path

    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    text = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "capture-ask.js").read_text(encoding="utf-8")
    start = text.index("function citationName(")
    body = text[start : text.index("\n}\n", start) + 2]
    script = (
        "const stripFrontmatter = (s) => s.replace(/^---\\n[\\s\\S]*?\\n---\\n/, '');\n"
        "const plainText = (s) => s.replace(/[*_#`]/g, '');\n"
        + body
        + f"\nconsole.log(JSON.stringify({json.dumps(contents)}.map((c) => citationName(c))));"
    )
    done = subprocess.run([node, "-e", script], capture_output=True, text=True, check=True)
    return json.loads(done.stdout)


def test_a_citation_label_is_cut_at_a_word_not_mid_word():
    """The marker's aria-label was `slice(0, 40)`: "follow up with her by em"."""
    names = _citation_names([
        "Met Dana at the meetup, follow up with her by email next week",
        "---\ntags: [a]\n---\n- [ ] buy a capo and restring the guitar before friday",
        "short note",
    ])
    assert names[0].endswith("…") and not names[0].rstrip("…").endswith(" by em"), names
    assert names[0].rstrip("…") in "Met Dana at the meetup, follow up with her by email next week"
    assert names[0].rstrip("…").split()[-1] in "Met Dana at the meetup, follow up with her by email next week".split()
    assert names[1].startswith("buy a capo"), names
    assert names[2] == "short note"
