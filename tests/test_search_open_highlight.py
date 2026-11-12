"""A note opened from the finder's results keeps the search terms marked
(WORLD_CLASS_PLAN 22.2). `flashEntry` clears the Notes filter so the card can
be found, and with it the highlight the filter's own cards have; the finder
now hands its terms over, `noteEngine.opened` holds them for that one note, and
`searchHighlightTerms(id)` returns them while no filter of its own is typed."""

from tests._app_js import app_js_text

TEXT = app_js_text()


def _body(signature: str) -> str:
    start = TEXT.index(signature)
    return TEXT[start:start + 1800]


def test_flash_entry_takes_terms_and_records_them_for_that_note():
    head = _body("async function flashEntry(id")
    assert "async function flashEntry(id, { terms = [] } = {})" in head
    assert "noteEngine.opened = { id, terms };" in head


def test_the_finder_hands_its_query_words_to_the_note_it_opens():
    assert 'note: (hit) => { switchTab("notes"); flashEntry(hit.id, { terms: finderState.terms() }); },' in TEXT
    helper = _body("finderState.terms = () =>")
    assert "parseNoteQuery(finderQuery)" in helper
    assert "query.phrases" in helper and "query.words" in helper


def test_the_card_asks_for_its_own_terms_and_a_typed_filter_wins():
    helper = _body("function searchHighlightTerms(")
    assert "function searchHighlightTerms(id = null)" in helper
    assert helper.index("noteSearch") < helper.index("noteEngine.opened")
    assert "noteEngine.opened.id === id" in helper
    assert "searchHighlightTerms(entry.id)" in TEXT
    assert "opened: { id: null, terms: [] }" in TEXT


def test_typing_in_the_notes_filter_forgets_the_opened_terms():
    handler = TEXT.split('$("note-search").addEventListener("input"', 1)[1][:400]
    assert "noteEngine.opened = { id: null, terms: [] };" in handler
