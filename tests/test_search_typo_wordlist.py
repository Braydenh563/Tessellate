"""VC8: the shipped English list in search typo tolerance. A query word absent
from `frontend/vendor/wordlist/en.txt` and one edit from a word the notebook
holds is a typo, so it is read as that word even where difflib's ratio is too
strict (a swapped pair in a four-letter word); a word that IS in the list is
never read as another (`tame` is not `time`). Recall at 10 on 30 misspelt
queries and 30 correct ones; numbers in CHANGELOG."""

from __future__ import annotations

import time

import pytest

from tessellate.ai import variants
from tessellate.core.database import Entry
from tessellate.search import search_manager

#: (typed, the word the note holds): four swaps in short words, then longer slips.
MISSPELT = [
    ("paer", "pear"), ("lmap", "lamp"), ("rsoe", "rose"), ("wlof", "wolf"), ("fren", "fern"),
    ("dvoe", "dove"), ("snad", "sand"), ("swna", "swan"), ("klin", "kiln"), ("tlie", "tile"),
    ("gardne", "garden"), ("tomtao", "tomato"), ("kithcen", "kitchen"), ("bicylce", "bicycle"),
    ("dentsit", "dentist"), ("pasport", "passport"), ("invioce", "invoice"), ("morgage", "mortgage"),
    ("umbrela", "umbrella"), ("notebok", "notebook"), ("harvset", "harvest"), ("libary", "library"),
    ("reciept", "receipt"), ("lavendr", "lavender"), ("pottey", "pottery"), ("sourdogh", "sourdough"),
    ("mushrom", "mushroom"), ("paintin", "painting"), ("thermstat", "thermostat"), ("lanter", "lantern"),
]
#: Real words one edit from a word the notebook holds: left alone.
REAL_NEIGHBOURS = [("tame", "time"), ("pare", "pear"), ("lamb", "lamp"), ("rise", "rose"), ("golf", "wolf")]
FILLER = (
    "time capsule buried by the shed", "tea tin on the high shelf", "rope for the boat trip", "wolfram sample list",
    "sandwich order for Friday", "tiles for the bathroom wall", "lambs at the farm", "pearl necklace repair",
)


@pytest.fixture()
def notebook(session):
    ids = {}
    for _, word in MISSPELT:
        entry = Entry(content=f"Remember the {word} this week, nothing else about it", tags="[]", ai_confidence=0)
        session.add(entry)
        session.flush()
        ids[word] = entry.id
    for _, word in REAL_NEIGHBOURS:
        if word not in ids:
            entry = Entry(content=f"A note on the {word} we kept", tags="[]", ai_confidence=0)
            session.add(entry)
            session.flush()
            ids[word] = entry.id
    for content in FILLER:
        session.add(Entry(content=content, tags="[]", ai_confidence=0))
    session.commit()
    return ids


def _recall(session, ids, pairs, column):
    hits = 0
    for pair in pairs:
        found = [e.id for e in search_manager.keyword_search(session, pair[0], limit=10)]
        hits += ids[pair[column]] in found
    return hits / len(pairs)


def test_the_typos_are_not_words():
    words = variants._english_all()
    assert words, "the shipped list must load"
    assert not [typed for typed, _ in MISSPELT if typed in words]
    assert all(real in words for real, _ in REAL_NEIGHBOURS)


def test_recall_at_10_on_the_thirty_misspelt_queries(notebook, session, capsys):
    recall = _recall(session, notebook, MISSPELT, 1)
    print(f"RECALL misspelt {recall:.3f}")
    assert recall >= 1.0


def test_correctly_spelt_queries_are_unchanged(notebook, session):
    right = [(word, word) for _, word in MISSPELT]
    assert _recall(session, notebook, right, 1) == 1.0
    for real, near in REAL_NEIGHBOURS:
        found = [e.id for e in search_manager.keyword_search(session, real, limit=10)]
        assert notebook[near] not in found, (real, near)


def test_the_list_loads_once_and_fast():
    variants._english_all.cache_clear()
    began = time.perf_counter()
    first = variants._english_all()
    cold = (time.perf_counter() - began) * 1000
    began = time.perf_counter()
    assert variants._english_all() is first
    print(f"LISTMS {cold:.1f}")
    assert cold < 50
