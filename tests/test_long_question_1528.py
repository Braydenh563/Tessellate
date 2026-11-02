"""A long pasted question is searched on its ask, not on the paste's opening
(INBOX 1528). The owner's chat takes 20,000 characters; the search reads at
most 300 words, and those used to be the first 300, so a paste with the ask at
its end was searched on whatever the paste began with."""

from __future__ import annotations

import pytest

from tessellate.entry import manager
from tessellate.search import long_question, search_manager

ASK = "What is the Quillfeather handshake and how does it greet the relay nodes?"

#: The paste is about a festival; nothing in it names the asked-about subject.
_FESTIVAL = (
    "The harvest festival needs lantern vendors, parking permits and a stage for the choir. "
    "Volunteers sort the cider barrels, the bunting and the pumpkin stalls before the gates open. "
    "The committee agreed the lantern vendors pay a small fee and the parking permits go to the stewards. "
    "The choir rehearses on Thursday while the cider barrels are counted and the bunting is hung. "
)


def _paste(position: str) -> str:
    body = _FESTIVAL * 22
    assert len(body.split()) > 300
    return {"last": f"{body}\n\n{ASK}", "first": f"{ASK}\n\n{body}", "middle": f"{body[: len(body) // 2]}\n\n{ASK}\n\n{body[len(body) // 2 :]}"}[position]


@pytest.fixture()
def notebook(session, fake_embeddings, monkeypatch):
    from datetime import date

    monkeypatch.setattr(search_manager, "_user_today", lambda _session: date(2026, 11, 2))
    defining = manager.create_entry(
        session, "The Quillfeather handshake is a three step greeting between relay nodes: ping, token, acknowledge."
    )
    for text in (
        "Harvest festival plan: lantern vendors, parking permits and the choir stage are booked.",
        "Festival cider barrels counted, bunting hung, pumpkin stalls sorted by the volunteers.",
        "Parking permits for the stewards and the lantern vendors fee, agreed by the committee.",
        "Choir rehearsal on Thursday, stage and bunting ready before the gates open.",
    ):
        manager.create_entry(session, text)
    return defining


@pytest.mark.parametrize("position", ["last", "first", "middle"])
def test_the_defining_note_leads_wherever_the_ask_sits(session, fake_embeddings, notebook, position):
    found = search_manager.retrieve_detailed(session, _paste(position), fake_embeddings, limit=3)
    assert found.entries and found.entries[0].id == notebook.id, [e.content[:40] for e in found.entries]


@pytest.mark.parametrize("position", ["last", "first", "middle"])
def test_the_search_text_carries_the_ask_and_stays_under_the_cap(session, notebook, position):
    text = search_manager.clip_query(session, _paste(position))
    assert "quillfeather handshake" in text.lower()
    assert len(text.split()) <= search_manager.SEARCH_QUERY_WORDS
    assert len(text) <= search_manager.SEARCH_QUERY_CHARS


def test_a_short_question_is_untouched(session, notebook):
    assert search_manager.clip_query(session, "a short question") == "a short question"
    just_under = " ".join(["word"] * search_manager.SEARCH_QUERY_WORDS)
    assert search_manager.clip_query(session, just_under) == just_under


def test_the_ask_is_the_last_sentence_that_reads_as_a_request():
    assert long_question.ask_of("Intro text here. Please summarise the budget. More text follows.") == "Please summarise the budget."
    assert long_question.ask_of("A. Is this fine? B. Why is it so? C. Closing remark.") == "Why is it so?"
    assert long_question.ask_of("Line one.\n\nLine two.\n\nThe closing line.") == "The closing line."


def test_distinctive_terms_use_the_index_weights(session, notebook):
    # Words in the fewest notes lead; "lantern" is in three notes and "cider" in two.
    terms = long_question.distinctive_terms(session, _paste("last"), skip=set(), count=3)
    assert len(terms) == 3 and "lantern" not in terms
    assert set(terms) <= {"cider", "barrels", "volunteers", "stewards", "stalls", "pumpkin", "sort", "sorted", "counted"}
    # a word no note holds is dropped, and the ask's own words are skipped
    assert long_question.distinctive_terms(session, "zzyzx cider cider", skip={"cider"}) == []
