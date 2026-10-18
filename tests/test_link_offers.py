"""Link offers: where a document names another note or document (VC5).

`POST /documents/link-offers` scans the text once with the vendored
FlashText against every name a `[[link]]` can resolve to, and answers the
first mention of each, so the editor can offer to link it. These tests hold
the rules that keep an offer from being noise or from rewriting the wrong
words: the span is the words as written, code and existing links are never
offered, a one-word name needs its own capital, and a note already linked
once is not offered again.
"""

from __future__ import annotations


def _document(client, title, content=""):
    response = client.post("/documents", json={"title": title, "content": content})
    assert response.status_code == 201, response.text
    return response.json()


def _note(client, content):
    response = client.post("/entries", json={"content": content})
    assert response.status_code in (200, 201), response.text
    return response.json()


def _offers(client, text, document_id=None):
    response = client.post("/documents/link-offers", json={"text": text, "document_id": document_id})
    assert response.status_code == 200, response.text
    return response.json()["offers"]


def _spans(text, offers):
    return [text[offer["start"] : offer["end"]] for offer in offers]


def test_a_document_title_in_the_text_is_offered_with_its_exact_span(client):
    _document(client, "Design system notes")
    text = "Before the review I read the design system notes again."
    offers = _offers(client, text)
    assert _spans(text, offers) == ["design system notes"]
    assert offers[0]["kind"] == "document"
    # The words as written are kept: the link is `[[Title|shown]]`.
    assert offers[0]["link"] == "[[Design system notes|design system notes]]"


def test_the_same_case_needs_no_alias(client):
    _document(client, "Design system notes")
    offers = _offers(client, "See Design system notes today.")
    assert offers[0]["link"] == "[[Design system notes]]"


def test_a_note_is_named_by_its_opening_line_without_the_heading_mark(client):
    _note(client, "# Quarterly roadmap\n\nThe plan for the year.")
    text = "Everything hangs on the quarterly roadmap this time."
    offers = _offers(client, text)
    assert _spans(text, offers) == ["quarterly roadmap"]
    assert offers[0]["kind"] == "note"
    assert offers[0]["link"] == "[[Quarterly roadmap|quarterly roadmap]]"


def test_only_the_first_mention_of_a_title_is_offered(client):
    _document(client, "Budget review")
    text = "The budget review ran long. After the budget review we left."
    offers = _offers(client, text)
    assert len(offers) == 1
    assert offers[0]["start"] == text.index("budget review")


def test_a_title_inside_a_code_fence_or_inline_code_is_not_offered(client):
    _document(client, "Budget review")
    fenced = "Notes:\n\n```\nbudget review\n```\n"
    inline = "Run `budget review` first."
    assert _offers(client, fenced) == []
    assert _offers(client, inline) == []


def test_an_existing_link_is_never_offered_again_or_inside_itself(client):
    _document(client, "Budget review")
    inside = "See [[Budget review]] for the figures."
    after = "See [[Budget review]] and then the budget review again."
    markdown = "See [the budget review](https://example.com/a) there."
    assert _offers(client, inside) == []
    assert _offers(client, after) == []
    assert _offers(client, markdown) == []


def test_a_title_inside_a_longer_word_is_not_a_mention(client):
    _document(client, "Roadmap plans")
    assert _offers(client, "The roadmap planserver is unrelated.") == []


def test_a_one_word_title_needs_its_own_capital(client):
    _document(client, "Tessellate")
    _document(client, "Budget")
    text = "I opened Tessellate and checked the budget."
    assert _spans(text, _offers(client, text)) == ["Tessellate"]


def test_a_short_title_is_never_offered(client):
    _document(client, "Ops")
    assert _offers(client, "Ops is on call tonight with Ops again.") == []


def test_the_documents_own_title_is_not_offered_to_itself(client):
    own = _document(client, "Budget review")
    text = "This budget review is mine."
    assert _offers(client, text, own["id"]) == []
    assert len(_offers(client, text)) == 1


def test_a_private_note_and_a_binned_document_are_never_offered(client, session):
    from tessellate.core.database import Entry

    note = _note(client, "# Secret plan\n\nhidden")
    session.get(Entry, note["id"]).is_private = True
    session.commit()
    doc = _document(client, "Binned idea")
    client.delete(f"/documents/{doc['id']}")
    text = "The secret plan and the binned idea."
    assert _offers(client, text) == []


def test_a_name_with_a_square_bracket_cannot_be_a_link_so_is_not_offered(client):
    _document(client, "Plan [v2] notes")
    assert _offers(client, "Read the plan [v2] notes now.") == []


def test_the_offers_are_capped_and_in_text_order(client):
    names = [f"Project {word} brief" for word in "alpha bravo charlie delta echo foxtrot golf hotel india juliet kilo lima mike".split()]
    for name in names:
        _document(client, name)
    text = " and ".join(name.lower() for name in reversed(names))
    offers = _offers(client, text)
    assert len(offers) == 12
    assert [offer["start"] for offer in offers] == sorted(offer["start"] for offer in offers)


def test_a_new_document_is_seen_at_once(client):
    text = "Later I will read the field guide."
    assert _offers(client, text) == []
    _document(client, "Field guide")
    assert _spans(text, _offers(client, text)) == ["field guide"]


def test_an_empty_text_answers_an_empty_list(client):
    assert _offers(client, "") == []
