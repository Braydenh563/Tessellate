"""A similar note says why it is similar (L20): the concrete overlap when
there is one (shared tag), else the plain meaning fallback."""

from __future__ import annotations


def test_a_shared_tag_is_the_reason(ai_client):
    a = ai_client.post("/entries", json={"content": "a funny scarecrow joke", "tags": ["jokes"]}).json()
    ai_client.post("/entries", json={"content": "another funny pun", "tags": ["jokes"]})
    rows = ai_client.get(f"/entries/{a['id']}/related").json()
    pun = next(r for r in rows if r["content"] == "another funny pun")
    assert "#jokes" in pun["link_reason"]


def test_no_overlap_falls_back_to_meaning(ai_client):
    a = ai_client.post("/entries", json={"content": "a funny scarecrow joke"}).json()
    ai_client.post("/entries", json={"content": "another funny pun"})
    rows = ai_client.get(f"/entries/{a['id']}/related").json()
    pun = next(r for r in rows if r["content"] == "another funny pun")
    assert pun["link_reason"]
