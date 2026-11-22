"""`GET /documents/outline`: the headings the Library's Contents index nests
under each document (INBOX 445 (1))."""

from __future__ import annotations
from tests._app_js import documents_text


def test_outline_lists_headings_with_zero_based_lines(client):
    client.post(
        "/documents",
        json={"title": "Plan", "content": "# Goal\ntext\n## Steps\nmore\n### Detail ###\n"},
    )
    rows = client.get("/documents/outline").json()
    assert [r["title"] for r in rows] == ["Plan"]
    assert rows[0]["headings"] == [
        {"line": 0, "level": 1, "text": "Goal"},
        {"line": 2, "level": 2, "text": "Steps"},
        {"line": 4, "level": 3, "text": "Detail"},
    ]


def test_a_comment_in_fenced_code_is_not_a_section(client):
    client.post(
        "/documents",
        json={"title": "Fenced", "content": "# Real\n```\n# not a heading\n```\n## Also real\n"},
    )
    heads = client.get("/documents/outline").json()[0]["headings"]
    assert [h["text"] for h in heads] == ["Real", "Also real"]


def test_a_code_document_has_no_headings(client):
    client.post("/documents", json={"title": "script", "content": "# a comment\nx = 1\n", "file_type": "py"})
    assert client.get("/documents/outline").json()[0]["headings"] == []


def test_outline_is_not_swallowed_by_the_document_id_route(client):
    assert client.get("/documents/outline").status_code == 200


def test_outline_carries_the_creation_date_for_by_month_grouping(client):
    """The Contents index's By month mode puts a document under the month it
    was created in, as notes are, so the row needs `created_at`."""
    client.post("/documents", json={"title": "Dated", "content": "# A\n"})
    row = client.get("/documents/outline").json()[0]
    assert row["created_at"][:4].isdigit() and "T" in row["created_at"]


def test_a_long_heading_ends_in_an_ellipsis_and_keeps_its_task_count():
    """The owner, 2026-11-05 (screenshot): long outline rows were clipped mid-word and their 0/5 counts were pushed
    out of sight. The words are their own box that ellipsizes; the count after it never shrinks. Measured 1440x900:
    the chip at 219 to 255 inside a row ending at 259."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    css = (root / "frontend" / "css" / "library-lazy.css").read_text(encoding="utf-8")
    js = documents_text()
    rule = css[css.index(".outline-text {") :].split("}")[0]
    for want in ("min-width: 0", "text-overflow: ellipsis", "white-space: nowrap", "overflow: hidden"):
        assert want in rule
    assert 'words.className = "outline-text"' in js and "button.textContent = heading.text" not in js


def test_the_documents_head_wraps_its_controls_rather_than_squeezing_the_new_pill():
    """The owner, 2026-11-05: "no gap between the templates and new arrow button". The split's slot shrank to 7 px
    under its 28 px caret, which lay 12 px over the template button."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    lazy = (root / "frontend" / "css" / "library-lazy.css").read_text(encoding="utf-8")
    side = lazy
    assert "flex: none" in lazy[lazy.index(".split-button {") :].split("}")[0]
    assert "flex: none" in lazy[lazy.index(".split-button > .split-button-slot {") :].split("}")[0]
    assert "flex-wrap: wrap" in side[side.index("#doc-sidebar-list > .sidebar-head {") :].split("}")[0]
