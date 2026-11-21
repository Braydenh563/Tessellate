"""`GET /entries?q=` is the notes list's literal text filter on the server (L810)."""
from tessellate.entry import manager


def _make(session):
    for text in ("Roadmap for the spring " + "x" * 400 + " zeta", "A grocery list", "Roadmap review notes"):
        manager.create_entry(session, text)


def test_q_filters_by_whole_text_in_list_order(client, session):
    _make(session)
    rows = client.get("/entries?q=zeta").json()
    assert [r["content"].startswith("Roadmap for") for r in rows] == [True]
    both = client.get("/entries?q=roadmap")
    assert both.headers["X-Total-Count"] == "2"
    assert len(both.json()) == 2


def test_q_matches_past_the_preview_and_pages(client, session):
    _make(session)
    row = client.get("/entries?q=zeta&preview=50").json()[0]
    assert row["content_truncated"] is True
    assert len(client.get("/entries?q=roadmap&limit=1").json()) == 1
    assert len(client.get("/entries?q=roadmap&limit=1&offset=1").json()) == 1


def test_q_without_a_term_keeps_the_plain_list(client, session):
    _make(session)
    assert len(client.get("/entries?q=%20").json()) == 3
    assert client.get("/entries?q=nomatchatall").json() == []
