"""A query word that is a real English word is left alone (LEDGER L-world-class-135, VC8).

The vocabulary typo fix replaced any word the notes never use with the closest word they do,
so "casual" in a notebook that says "causal" searched for the other word and showed notes
the person did not ask about. The English word list (`variants.english`) now says which
absent words are words: those are not typos, and the search says no instead of guessing.

Measured on the 30 misspelt queries below (a note each) and 30 correctly spelt words that
sit one slip from a word a note holds:

    recall at 10 on the misspelt     before 16 / 30   after 30 / 30
    wrong notes for the spelt words  before 19 / 30   after  0 / 30
"""

from __future__ import annotations

import pytest

#: (the word a note holds, the misspelt query that should find it)
MISSPELT = [
    ("gardening", "gardning"), ("kitchen", "kichen"), ("history", "histroy"), ("calendar", "calender"),
    ("library", "libary"), ("meeting", "meetng"), ("holiday", "holdiay"), ("invoice", "invoce"),
    ("battery", "batery"), ("network", "netwrok"), ("recipe", "recipie"), ("project", "projcet"),
    ("journal", "jurnal"), ("science", "sciense"), ("market", "markat"), ("pocket", "pockat"),
    ("window", "windwo"), ("budget", "budgat"), ("bridge", "brigde"), ("weather", "wether"),
    ("receive", "recieve"), ("separate", "seperate"), ("definitely", "definately"), ("tomorrow", "tomorow"),
    ("necessary", "neccessary"), ("occasion", "ocassion"), ("beginning", "begining"), ("achieve", "acheive"),
    ("environment", "enviroment"), ("restaurant", "restaraunt"),
]

#: (the word a note holds, a correctly spelt word the notebook never uses, one slip away)
SPELT = [
    ("causal", "casual"), ("angle", "angel"), ("lesson", "lessen"), ("principal", "principle"),
    ("dessert", "desert"), ("affect", "effect"), ("complement", "compliment"), ("council", "counsel"),
    ("stationary", "stationery"), ("quiet", "quite"), ("alter", "altar"),
    ("adopt", "adapt"), ("device", "devise"), ("emigrate", "immigrate"), ("flaunt", "flout"),
    ("scent", "scene"), ("feat", "feet"), ("personal", "personnel"), ("proceed", "precede"),
    ("sensor", "censor"), ("elicit", "illicit"), ("farther", "further"), ("formally", "formerly"),
    ("hoard", "horde"), ("later", "latter"), ("mantel", "mantle"), ("naval", "navel"),
    ("peak", "peek"), ("statue", "statute"), ("capital", "capitol"),
]


def _hits(client, q: str) -> list:
    reply = client.get("/search", params={"q": q, "hybrid": "false"})
    assert reply.status_code == 200, reply.text
    return [h for h in reply.json()["hits"] if h["kind"] == "note"]


@pytest.fixture()
def notebook(client):
    ids = {}
    for word in dict.fromkeys([m[0] for m in MISSPELT] + [s[0] for s in SPELT]):
        ids[word] = client.post("/entries", json={"content": f"Notes about the {word} this week"}).json()["id"]
    return ids


def test_a_misspelt_word_still_finds_its_note(client, notebook):
    missed = [typed for word, typed in MISSPELT if notebook[word] not in [h["id"] for h in _hits(client, typed)[:10]]]
    print("recall at 10:", len(MISSPELT) - len(missed), "of", len(MISSPELT), "missed", missed)
    assert missed == []


def test_a_real_word_the_notes_never_use_is_not_read_as_a_typo(client, notebook):
    shown = [real for _, real in SPELT if _hits(client, real)]
    print("false hits:", len(shown), "of", len(SPELT), shown)
    assert shown == []
