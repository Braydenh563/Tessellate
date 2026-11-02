"""`GET /entries?preview=` (audit 1031 BK10): each row's first characters.

The notes list keeps asking for whole notes (client-side search, the card body
and a copy all read the text), so the default is unchanged; a caller that draws
a row's first lines asks for less. The tag reasons are a pure function of the
text, so a list reads each note's answer once.
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


def test_tag_reasons_are_remembered_per_text():
    routes_entries._cached_reasons.cache_clear()
    first = routes_entries._tag_reasons("I went running and squats today", ["running"])
    again = routes_entries._tag_reasons("I went running and squats today", ["running"])
    assert first == again
    assert routes_entries._cached_reasons.cache_info().hits == 1
    assert routes_entries._tag_reasons("", ["running"]) == {}
