"""Browser bookmarks files in and out (DOCUMENTS_PLAN L6): `repo/bookmarks_html.py` and its two routes."""

from __future__ import annotations

from tessellate.repo import bookmarks_html

#: What Chrome and Firefox write: nested DL lists, a folder as H3 then DL, tags never closed.
CHROME = """<!DOCTYPE NETSCAPE-Bookmark-file-1>
<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">
<TITLE>Bookmarks</TITLE>
<H1>Bookmarks</H1>
<DL><p>
    <DT><H3 ADD_DATE="1700000000" PERSONAL_TOOLBAR_FOLDER="true">Bookmarks bar</H3>
    <DL><p>
        <DT><A HREF="https://example.com/a" ADD_DATE="1700000100" ICON="data:image/png;base64,xx">Example &amp; A</A>
        <DT><H3>Work</H3>
        <DL><p>
            <DT><A HREF="https://example.com/b" ADD_DATE="1700000200">Deep b</A>
            <DT><A HREF="javascript:alert(1)">Bookmarklet</A>
        </DL><p>
        <DT><A HREF="https://example.com/c">C</A>
    </DL><p>
    <DT><A HREF="example.org/top">Top level</A>
</DL><p>
"""


def test_the_parser_follows_folders_skips_unsafe_rows_and_keeps_dates() -> None:
    rows, skipped = bookmarks_html.parse(CHROME)
    got = [(r["title"], r["url"], r["group_name"]) for r in rows]
    assert got == [
        ("Example & A", "https://example.com/a", "Bookmarks bar"),
        ("Deep b", "https://example.com/b", "Bookmarks bar/Work"),
        ("C", "https://example.com/c", "Bookmarks bar"),
        ("Top level", "https://example.org/top", ""),
    ]
    assert skipped == 1
    assert rows[0]["added"] == "1700000100"


def test_a_slash_in_a_folders_own_name_is_not_a_level() -> None:
    rows, _ = bookmarks_html.parse('<DL><p><DT><H3>A/B</H3><DL><p><DT><A HREF="https://x.test/">x</A></DL><p></DL>')
    assert rows[0]["group_name"] == "A-B"


def test_render_nests_a_group_path_and_escapes() -> None:
    html = bookmarks_html.render([
        {"url": "https://x.test/?a=1&b=2", "title": "<b>x</b>", "group_name": "Work/Reading"},
        {"url": "https://y.test/", "title": "", "group_name": ""},
    ])
    assert html.startswith("<!DOCTYPE NETSCAPE-Bookmark-file-1>")
    assert "<H3>Work</H3>" in html and "<H3>Reading</H3>" in html
    assert "&lt;b&gt;x&lt;/b&gt;" in html and "a=1&amp;b=2" in html
    assert ">https://y.test/</A>" in html  # no title: the address reads
    again, _ = bookmarks_html.parse(html)
    assert [(r["url"], r["group_name"]) for r in again] == [("https://y.test/", ""), ("https://x.test/?a=1&b=2", "Work/Reading")]


def test_import_adds_skips_twins_and_exports_round_trip(client) -> None:
    client.post("/bookmarks", json={"url": "https://example.com/a", "title": "Mine"})
    got = client.post("/bookmarks/import", json={"html": CHROME}).json()
    assert got["found"] == 4 and got["added"] == 3 and got["duplicates"] == 1 and got["skipped"] == 1
    assert len(got["ids"]) == 3
    listed = client.get("/bookmarks").json()
    by_url = {b["url"]: b for b in listed}
    assert by_url["https://example.com/a"]["title"] == "Mine"
    assert by_url["https://example.com/b"]["group_name"] == "Bookmarks bar/Work"
    assert by_url["https://example.com/b"]["created_at"].startswith("2023-11-14")
    again = client.post("/bookmarks/import", json={"html": CHROME}).json()
    assert again["added"] == 0 and again["duplicates"] == 4

    out = client.get("/bookmarks/export")
    assert out.status_code == 200 and "attachment" in out.headers["content-disposition"]
    rows, _ = bookmarks_html.parse(out.text)
    assert {r["url"] for r in rows} == set(by_url)


def test_import_refuses_what_is_not_a_bookmarks_file_politely(client) -> None:
    assert client.post("/bookmarks/import", json={"html": ""}).status_code == 422
    got = client.post("/bookmarks/import", json={"html": "<p>just a page</p>"}).json()
    assert got["added"] == 0 and got["found"] == 0


def test_the_bookmarks_menu_has_import_and_export_wired() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "frontend"
    html = (root / "index.html").read_text(encoding="utf-8")
    js = (root / "js" / "library.js").read_text(encoding="utf-8")
    for needle in ('id="bookmark-import"', 'id="bookmark-export"', 'id="bookmark-import-file"'):
        assert needle in html, needle
    assert 'renderBookmarks.file.load(input.files?.[0])' in js and "/bookmarks/import" in js and "/bookmarks/export" in js
    assert "pushUndo(`Imported" in js
