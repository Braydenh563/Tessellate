"""`[[Target|Shown]]`: one meaning in every place a wiki link is read.

The target is the part before the first `|`; the part after is only what is
drawn. Before this, `wiki_link_targets` handed the whole `Target|Shown` string
to `find_by_wiki_name`, which looked for a note starting with it and found
none (no link made), while a document's backlinks panel compared the whole
inner text against the title (no backlink) and the note references row
looked for the literal `[[Title]]` (reported as a bare mention). Three
readers, three answers for the same text.
"""

from __future__ import annotations

from tessellate.entry import manager


def _note(client, content):
    return client.post("/entries", json={"content": content}).json()


def _document(client, title, content=""):
    response = client.post("/documents", json={"title": title, "content": content})
    assert response.status_code == 201, response.text
    return response.json()


def test_the_target_is_the_part_before_the_bar():
    assert manager.wiki_link_targets("see [[bread proving|the dough note]]") == ["bread proving"]


def test_a_target_named_with_and_without_an_alias_is_one_target():
    found = manager.wiki_link_targets("[[bread]] then [[Bread|loaf]] then [[bread | toast]]")
    assert found == ["bread"]


def test_an_empty_target_or_an_empty_alias_is_handled():
    assert manager.wiki_link_targets("[[|only shown]]") == []
    assert manager.wiki_link_targets("[[bread|]]") == ["bread"]


def test_an_aliased_link_creates_a_real_link(client):
    target = _note(client, "bread proving times vary")
    source = _note(client, "check [[bread proving|the dough note]] before baking")
    linked = client.get(f"/entries/{source['id']}").json()["links"]
    assert [link["entry_id"] for link in linked] == [target["id"]]


def test_find_by_wiki_name_reads_an_alias_the_same_way(client, session):
    target = _note(client, "kayaking trip in March")
    found = manager.find_by_wiki_name(session, "kayaking trip|the paddle")
    assert found is not None and found.id == target["id"]


def test_a_document_backlink_counts_an_aliased_link(client):
    document = _document(client, "Roadmap")
    _note(client, "next steps live in [[Roadmap|the plan]] now")
    body = client.get(f"/documents/{document['id']}/backlinks").json()
    assert len(body["links"]) == 1
    assert body["mentions"] == []


def test_a_note_reference_row_says_links_to_it_for_an_aliased_link(client):
    target = _note(client, "The roof quote")
    source = _note(client, "chase [[The roof quote|the builder]] on Monday")
    items = client.get(f"/entries/{target['id']}/references").json()["items"]
    assert [(row["id"], row["how"]) for row in items] == [(source["id"], "links to it")]


def test_links_to_reads_the_target_only():
    from tessellate.api import routes_entries_refs

    assert routes_entries_refs._links_to("x [[The roof quote|the builder]]", "the roof quote")
    assert not routes_entries_refs._links_to("x [[The roof quote and more|y]]", "the roof quote")


def test_the_shown_part_is_what_a_label_reads():
    assert manager.plain_label("see [[Bread proving|the dough note]] today") == "see the dough note today"
    assert manager.plain_label("[[Roadmap]] first") == "Roadmap first"
    assert manager.wiki_plain("a [[A|B]] and [[C]]") == "a B and C"
    assert manager.wiki_plain("[[A|]]") == "A"


def test_previews_show_the_shown_text():
    from tessellate.ai import extractor
    from tessellate.api import routes_entries, routes_graph

    assert routes_entries._preview("go [[A|B]]") == "go B"
    assert extractor._short_preview("go [[A|B]]") == "go B"
    assert routes_graph._preview_line("go [[A|B]]") == "go B"
