"""A note's `---` properties block is never printed as its words (GRAPH_PLAN,
"After KG1 to KG9").

KG7 fixed the graph label, the link chip and the mentions line; a search
snippet, the Library's card preview, a reminder's note line, a document's card
and a contradiction's excerpt still quoted the raw opening, `--- status: open
---`, as if it were prose.
"""

from __future__ import annotations

from datetime import timedelta

from tessellate.core.database import utcnow
from tessellate.entry import manager_text
from tessellate.search import engine
from tests import _js_scope

NOTE = "---\nstatus: open\ntype: meeting\n---\n# Kiln plan\n\nFire on Thursday."
UNTITLED = "---\nstatus: open\n---\nFire the kiln on Thursday."


def _no_block(text: str) -> None:
    assert "status: open" not in text, text
    assert not text.startswith("---"), text


def test_remove_title_reads_past_the_block():
    out = manager_text.remove_title(NOTE)
    assert "# Kiln plan" not in out and "Fire on Thursday." in out


def test_the_library_card_preview_has_no_block(client):
    client.post("/entries", json={"content": NOTE})
    client.post("/entries", json={"content": UNTITLED})
    notes = [i for i in client.get("/library").json()["items"] if i["kind"] == "note"]
    assert len(notes) == 2
    for item in notes:
        _no_block(item["preview"])
        _no_block(item["title"])
    assert {i["preview"] for i in notes} == {"Fire on Thursday.", "Fire the kiln on Thursday."}


def test_the_binned_preview_has_no_block(client):
    made = client.post("/entries", json={"content": NOTE}).json()
    client.delete(f"/entries/{made['id']}")
    binned = [i for i in client.get("/library").json()["items"] if i["kind"] == "archived"]
    assert binned
    for item in binned:
        _no_block(item["preview"])


def test_a_search_snippet_has_no_block(client, session):
    client.post("/entries", json={"content": UNTITLED})
    hits = engine.search(session, "kiln", ctx=None)
    assert hits
    for hit in hits:
        _no_block(hit.snippet)
    assert hits[0].snippet == "Fire the kiln on Thursday."


def test_a_search_snippet_for_a_word_only_the_block_has(client, session):
    client.post("/entries", json={"content": UNTITLED})
    for hit in engine.search(session, "status", ctx=None):
        _no_block(hit.snippet)


def test_a_reminders_note_line_has_no_block(client):
    made = client.post("/entries", json={"content": UNTITLED}).json()
    due = (utcnow() + timedelta(days=1)).isoformat()
    row = client.post("/reminders", json={"text": "x", "due_at": due, "entry_id": made["id"]}).json()
    _no_block(row["entry_preview"])
    assert row["entry_preview"].startswith("Fire the kiln")


def test_a_documents_card_preview_has_no_block(client):
    client.post("/documents", json={"title": "Plan", "content": "---\nstatus: open\n---\n\nFire the kiln."})
    docs = [i for i in client.get("/library").json()["items"] if i["kind"] == "document"]
    assert docs
    _no_block(docs[0]["preview"])
    assert docs[0]["preview"].startswith("Fire the kiln")


def test_apply_title_puts_the_heading_after_the_block():
    out = manager_text.apply_title(UNTITLED, "Kiln day")
    assert out == "---\nstatus: open\n---\n# Kiln day\nFire the kiln on Thursday."
    assert manager_text.apply_title(NOTE, "Kiln day").startswith("---\nstatus: open\ntype: meeting\n---\n# Kiln day\n")
    assert manager_text.remove_title(out).endswith("---\nFire the kiln on Thursday.")


def test_a_search_hit_is_titled_by_the_line_after_the_block(client, session):
    client.post("/entries", json={"content": NOTE})
    hits = engine.search(session, "kiln", ctx=None)
    assert hits and hits[0].title == "Kiln plan"


def test_an_ask_card_has_no_block():
    from tessellate.ai import cards

    item = cards._note_item({"id": 3, "content": UNTITLED})
    assert item["label"].startswith("Fire the kiln")
    assert item["snippet"] == "Fire the kiln on Thursday."


def test_the_frontends_raw_content_clips_read_past_the_block():
    """The places that cut `entry.content` for a label read it through
    `stripFrontmatter` first (it is one function, shell-reminders.js)."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "frontend" / "js"
    # The palette is not here since INBOX 666: it lists commands and places
    # only, so it shows no note content to clip (the line below still holds
    # it to that).
    #: The re-evaluate card moved from lightbox.js to entry-card.js (unslop 15, boot bytes).
    for name in ("categories-panel", "graph", "entry-card", "notes-list"):
        text = (root / f"{name}.js").read_text(encoding="utf-8")
        assert "stripFrontmatter(" in text, name
    assert "entry.content.slice(0, 60)" not in (root / "graph.js").read_text(encoding="utf-8")
    assert "e.content.slice(0, 55)" not in _js_scope.unwrapped((root / "app-palette.js").read_text(encoding="utf-8"))


def test_a_contradictions_excerpt_has_no_block():
    from tessellate.ai import tensions

    _no_block(tensions._excerpt(UNTITLED))


def test_the_dashboards_note_widgets_read_past_the_block():
    """Recently added, the random note and the unfinished-checklists title each
    cut a note's raw text; with a `---` block first they showed `---` and the
    fields as the note's words (found by `scratchpad/ui-sweeps/deepflows.js`,
    which opened the dashboard on a notebook with properties)."""
    from pathlib import Path

    text = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "dashboard.js").read_text(encoding="utf-8")
    assert "const raw = stripFrontmatter(entry.content || \"\")" in text
    assert "truncateMarkdownSafe(stripFrontmatter(note.content), 239)" in text
    #: The unfinished-checklists title is a note's name, which `noteNamePlain` (INBOX 820) cuts
    #: past the block itself; the shared helper replaced a hand-rolled `.split("\n")[0]`.
    assert "noteNamePlain(row.entry.content)" in text
    helper = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "chat-attach.js").read_text(encoding="utf-8")
    assert "stripFrontmatter(String(content ?? \"\"))" in helper
