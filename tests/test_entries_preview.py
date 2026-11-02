"""`GET /entries?preview=` (audit 1031 BK10): each row's first characters.

The Notes list asks for `preview=300` (INBOX 1525: its search is the index's,
and an open, an edit or a save fetches the whole note by id), so the default
is unchanged for every other caller; a caller that draws a row's first lines
asks for less. The tag reasons are a pure function of the text, so a list
reads each note's answer once.
"""

from __future__ import annotations

from tessellate.api import routes_entries

LONG = "# Plan\n\n" + " ".join(f"word{i}" for i in range(400))


def test_default_list_carries_the_whole_text(client):
    made = client.post("/entries", json={"content": LONG, "defer_filing": True}).json()
    rows = client.get("/entries?limit=5").json()
    row = next(r for r in rows if r["id"] == made["id"])
    assert row["content"] == LONG
    assert row["content_truncated"] is False


def test_preview_cuts_at_a_word_and_says_so(client):
    made = client.post("/entries", json={"content": LONG, "defer_filing": True}).json()
    row = next(r for r in client.get("/entries?limit=5&preview=120").json() if r["id"] == made["id"])
    assert row["content_truncated"] is True
    assert len(row["content"]) <= 120
    assert LONG.startswith(row["content"])
    assert not row["content"].endswith("wor")  # a word, not half of one
    assert row["title"] == "Plan"
    assert row["content_hash"] == made["content_hash"]  # the whole text's


def test_a_short_note_is_not_marked_truncated(client):
    made = client.post("/entries", json={"content": "short", "defer_filing": True}).json()
    row = next(r for r in client.get("/entries?preview=120").json() if r["id"] == made["id"])
    assert row["content"] == "short" and row["content_truncated"] is False


def test_preview_works_on_the_ids_read_and_is_bounded(client):
    made = client.post("/entries", json={"content": LONG, "defer_filing": True}).json()
    rows = client.get(f"/entries?ids={made['id']}&preview=50").json()
    assert rows[0]["content_truncated"] is True and len(rows[0]["content"]) <= 50
    assert client.get("/entries?preview=99999").status_code == 422
    assert client.get("/entries?preview=-1").status_code == 422


def test_a_preview_row_carries_the_numbers_of_the_whole_text(client):
    text = "# Plan\n\n- [ ] one\n- [x] two\n1. [ ] three\n\n" + " ".join(["filler"] * 300)
    made = client.post("/entries", json={"content": text, "defer_filing": True}).json()
    row = next(r for r in client.get("/entries?preview=60").json() if r["id"] == made["id"])
    assert row["content_truncated"] is True and len(row["content"]) <= 60
    assert (row["word_count"], row["tasks_open"], row["tasks_done"]) == (len(text.split()), 2, 1)
    whole = next(r for r in client.get("/entries").json() if r["id"] == made["id"])
    assert whole["word_count"] is None  # a whole row is counted by whoever holds it


def test_a_meeting_is_sent_whole_because_its_card_reads_the_sections(client):
    text = "---\ntype: meeting\n---\n# Weekly\n\n" + " ".join(["filler"] * 300) + "\n\n## Decisions\n\n- ship it"
    made = client.post("/entries", json={"content": text, "defer_filing": True}).json()
    row = next(r for r in client.get("/entries?preview=60").json() if r["id"] == made["id"])
    assert row["properties"].get("type") == ["meeting"]
    assert row["content"] == text and row["content_truncated"] is False


def test_tag_reasons_are_remembered_per_text():
    routes_entries._cached_reasons.cache_clear()
    first = routes_entries._tag_reasons("I went running and squats today", ["running"])
    again = routes_entries._tag_reasons("I went running and squats today", ["running"])
    assert first == again
    assert routes_entries._cached_reasons.cache_info().hits == 1
    assert routes_entries._tag_reasons("", ["running"]) == {}
