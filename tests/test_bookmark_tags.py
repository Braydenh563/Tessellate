"""Tags on bookmarks (DOCUMENTS_PLAN L6): a link in many places at once, which one group cannot be."""

from __future__ import annotations

from pathlib import Path

from tessellate.repo import bookmarks, bookmarks_html


def test_tags_are_cleaned_once_and_kept_in_the_order_given() -> None:
    assert bookmarks.clean_tags(["#Read", " read ", "to  try", "", "a,b"]) == "Read,to try,a b"
    assert bookmarks.clean_tags("one, Two ,one,#three") == "one,Two,three"
    assert bookmarks.clean_tags([f"t{i}" for i in range(30)]).count(",") == bookmarks.MAX_TAGS - 1
    assert len(bookmarks.clean_tags(["x" * 100])) == bookmarks.MAX_TAG_CHARS
    assert bookmarks.tag_list("") == [] and bookmarks.tag_list("a,b") == ["a", "b"]


def test_tags_save_edit_and_come_back_as_a_list(client) -> None:
    made = client.post("/bookmarks", json={"url": "https://a.test/", "tags": ["Cooking", "later"]}).json()
    assert made["tags"] == ["Cooking", "later"]
    assert client.get("/bookmarks").json()[0]["tags"] == ["Cooking", "later"]
    # Left out, tags stay; sent empty, they clear.
    assert client.put(f"/bookmarks/{made['id']}", json={"title": "A"}).json()["tags"] == ["Cooking", "later"]
    assert client.put(f"/bookmarks/{made['id']}", json={"tags": ["#one", "one", "two"]}).json()["tags"] == ["one", "two"]
    assert client.put(f"/bookmarks/{made['id']}", json={"tags": []}).json()["tags"] == []
    assert client.post("/bookmarks", json={"url": "https://b.test/"}).json()["tags"] == []


def test_a_bookmarks_file_carries_tags_both_ways(client) -> None:
    html = '<DL><p><DT><A HREF="https://x.test/" TAGS="recipes, soup">x</A><DT><A HREF="https://y.test/">y</A></DL>'
    rows, _ = bookmarks_html.parse(html)
    assert rows[0]["tags"] == "recipes, soup" and rows[1]["tags"] == ""
    got = client.post("/bookmarks/import", json={"html": html}).json()
    assert got["added"] == 2
    by_url = {b["url"]: b for b in client.get("/bookmarks").json()}
    assert by_url["https://x.test/"]["tags"] == ["recipes", "soup"]
    out = client.get("/bookmarks/export").text
    assert 'TAGS="recipes,soup"' in out and out.count("TAGS=") == 1


def test_a_tag_finds_the_link_in_search(client) -> None:
    client.post("/bookmarks", json={"url": "https://zzz.test/", "title": "Plain page", "tags": ["quokka"]})
    hits = client.get("/search", params={"q": "quokka"}).json()["hits"]
    assert any(h["kind"] == "bookmark" for h in hits), hits


def test_the_links_tab_filters_and_edits_by_tag() -> None:
    root = Path(__file__).resolve().parents[1] / "frontend"
    js = (root / "js" / "library.js").read_text(encoding="utf-8")
    html = (root / "index.html").read_text(encoding="utf-8")
    assert 'id="bookmark-tags-input"' in html
    for needle in ("bookmarkScope.tag", "tags: tagsInput.value", "b.tags", "bookmark-tag-chip"):
        assert needle in js, needle
