"""L121 (INBOX 744 b): "test notes" over ten notes about test says the count and quotes every
one of them, so no matching record is left unmentioned; the grounding cites all ten."""

from tests import _seed_1031c as seed_c

TITLES = ["test", "test board", "test draft", "test notes plan", "test two", "test three", "test four", "test five", "test six", "test seven"]


def test_every_matching_note_is_said_and_cited(client, session, monkeypatch):
    from tessellate.entry import manager

    for t in TITLES:
        manager.create_entry(session, f"# {t}\n\nSome words about {t} and testing things.", category_name="Personal")
    session.commit()
    said, events = seed_c.asker(client, monkeypatch)("test notes")
    assert said.startswith("You have ten notes about test")
    for t in TITLES:
        assert f"about {t} and testing" in said, t
    cited = {r["note_id"] for e in events if e.get("type") == "grounding" for r in e.get("sentences") or []}
    assert len(cited) == 10
