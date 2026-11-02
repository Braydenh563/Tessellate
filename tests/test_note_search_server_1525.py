"""INBOX 1525 (audit 1031 BK10): the Notes filter box asks the index for a note's words, not the page's rows."""

from __future__ import annotations


def _note(client, text):
    return client.post("/entries", json={"content": text, "defer_filing": True}).json()["id"]


def _ids(client, q):
    return client.get("/search", params={"q": q, "kind": "note", "ids_only": "true"}).json()["ids"]


def test_a_word_deep_in_a_long_note_is_found(client):
    deep = _note(client, "Start of a long note. " + "filler words here. " * 200 + "the zanzibar clove harvest")
    other = _note(client, "A short note about tea")
    assert deep in _ids(client, "zanzibar")
    assert other not in _ids(client, "zanzibar")


def test_every_word_must_be_there_and_a_prefix_counts(client):
    both = _note(client, "Gardening notes about tomatoes")
    one = _note(client, "Gardening notes about beans")
    assert _ids(client, "garden tomat") == [both]
    assert one in _ids(client, "garden")


def test_a_phrase_and_an_exclusion(client):
    a = _note(client, "slow cooked rice with beans")
    b = _note(client, "rice and then beans")
    assert _ids(client, '"rice with beans"') == [a]
    assert _ids(client, "rice -with") == [b]


def test_only_an_exclusion_lists_the_rest(client):
    a = _note(client, "pasta night")
    b = _note(client, "rice night")
    assert a not in _ids(client, "-pasta")
    assert b in _ids(client, "-pasta")


def test_nothing_to_match_is_null_and_nothing_loose_is_added(client):
    _note(client, "alpha beta")
    #: The list sends words only (its own parser takes `tag:` and the rest), and the server reads them literally
    #: (INBOX 1525 review): `tag:x` is text nobody wrote, not an operator, so it matches nothing rather than null.
    assert client.get("/search", params={"q": "tag:x", "ids_only": "true"}).json()["ids"] == []
    assert client.get("/search", params={"q": "", "ids_only": "true"}).json()["ids"] is None
    assert client.get("/search", params={"q": "  - ", "ids_only": "true"}).json()["ids"] is None
    # no "any of the words" fallback, no typo fix
    assert _ids(client, "alpha gamma") == []
    assert _ids(client, "alhpa") == []


# --- the page ---------------------------------------------------------------


from tests._app_js import with_pieces  # noqa: E402


def _list_js() -> str:
    return with_pieces("notes-list.js")


def test_the_filter_box_asks_the_index_for_a_notes_words():
    text = _list_js()
    start = text.index("function matchesSearch(entry)")
    block = text[start : text.index("\n}\n", start)]
    assert "noteEngine.bodyIds(query)" in block
    assert "ids_only=true" in text and 'clipFor("search", text)' in text


def test_a_save_or_a_reload_forgets_the_answer():
    text = _list_js()
    assert text.count('noteEngine.body.q = noteEngine.body.pending = "";') == 2
    load = text[text.index("async function _loadEntries()") :][:600]
    assert "noteEngine.body.q = " in load
