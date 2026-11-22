"""The suggestions inbox's decisions bound what they store (sweep 1004): each
signal name is kept in the learning table for ever, so a name is a word, not
a document."""

from __future__ import annotations


def test_a_dismissal_with_a_huge_signal_name_is_refused(client):
    #: The inbox dismisses through `/learned/corrections` (suggestions-inbox.js
    #: `inboxCorrection`); the bound moved there with the dead
    #: `/suggestions/merges/dismiss` route.
    body = {"kind": "dismiss_merge", "subject": {"a": 1, "b": 2, "signals": ["x" * 5000]}}
    assert client.post("/learned/corrections", json=body).status_code == 422
    body = {"kind": "open_after_ask", "subject": {"question": "x" * 9000, "entry_id": 1}}
    long_subject = client.post("/learned/corrections", json=body)
    assert long_subject.status_code == 422
    body = {"keep_id": 1, "merge_id": 2, "signals": ["x" * 5000]}
    assert client.post("/suggestions/merges/accept", json=body).status_code == 422


def test_a_topic_summary_term_is_a_word_not_a_document(client):
    body = {"ids": [1], "terms": ["x" * 5000]}
    assert client.post("/graph/topics/summary", json=body).status_code == 422


def test_ordinary_signal_names_still_pass(client):
    body = {"kind": "dismiss_merge", "subject": {"a": 1, "b": 2, "signals": ["shared_note", "same_initial"]}}
    assert client.post("/learned/corrections", json=body).status_code == 201
